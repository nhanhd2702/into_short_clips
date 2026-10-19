"""Find the most viral-worthy highlights in a transcript.

Logic ported from ViralVadoo's transcript_analysis/highlight_generator.py:
  - content-type / density detection
  - chunking for long videos with overlap
  - virality-criteria prompt
  - score-based dedupe with overlap suppression

The LLM call is pluggable via the `llm_fn` argument so the same prompts can
drive either MuAPI (default, --mode api) or a direct local LLM client
(--mode local).
"""
import json
import re
from typing import Callable, Dict, List, Optional, Tuple

from . import muapi


LLMFn = Callable[[str], str]


CONTENT_TYPE_PROMPT = """Analyze this video transcript sample and classify the content type.
Choose one: podcast, interview, tutorial, lecture, commentary, debate, vlog, other.
Also estimate content density: low (mostly filler/chit-chat), medium, or high (dense info/stories).
Respond with JSON only: {"content_type": "...", "density": "..."}"""


VIRALITY_CRITERIA = """
Virality signals to prioritize (ranked by impact):
1. HOOK MOMENTS — statements that create immediate curiosity ("The secret is...", "Nobody talks about...", "I was completely wrong about...")
2. EMOTIONAL PEAKS — genuine surprise, laughter, anger, vulnerability, excitement; raw unscripted reactions
3. OPINION BOMBS — strong, polarizing or counter-intuitive statements that trigger agree/disagree
4. REVELATION MOMENTS — surprising facts, stats, or confessions that reframe how the viewer thinks
5. CONFLICT/TENSION — disagreement, pushback, or a problem being confronted head-on
6. QUOTABLE ONE-LINERS — a sentence that works as a standalone quote card
7. STORY PEAKS — the climax or twist of an anecdote; the payoff moment
8. PRACTICAL VALUE — a concrete tip, hack, or insight the viewer can immediately apply
"""


HIGHLIGHT_SYSTEM_PROMPT = """You are an elite short-form video editor who has studied thousands of viral clips on TikTok, Instagram Reels, and YouTube Shorts. You know exactly what makes viewers stop scrolling, watch to the end, and share.

{virality_criteria}

Content type: {content_type} | Density: {density}

Your task: identify the most viral-worthy highlights from the transcript.

Rules:
- Every highlight must open with a strong HOOK — a line that grabs attention within the first 3 seconds
- Duration sweet spot: 50-70 seconds (target ~60 seconds). Each clip should deliver a cohesive, meaningful story or insight.
- STRICTLY EXCLUDE CHANNEL INTROS & CALLS-TO-ACTION: Never start a clip with channel welcomes, host greetings, teasers, or subscription reminders (e.g. "Xin chào các bạn", "Chào mừng quay trở lại", "Hãy like và đăng ký kênh", "Welcome back", "Please subscribe", sponsor plugs). The clip MUST start directly where the actual valuable content or argument begins.
- COHESIVE SPEECH BOUNDARIES: Align start_time and end_time to full, finished sentences. Never start or end a clip mid-sentence or mid-word.
- Clips must not overlap significantly with each other
- Score 0-100 on viral potential (not general quality)
- {num_clips_instruction}
- For each highlight, identify the single best "hook_sentence" — the opening line that would make someone stop scrolling
- Explain in one sentence why this clip is viral ("virality_reason")

Respond ONLY with valid JSON (no markdown, no explanation):
{{"highlights":[{{"title":"string","start_time":float,"end_time":float,"score":int,"hook_sentence":"string","virality_reason":"string"}}]}}"""


CHUNK_SIZE_SECONDS = 420       # 7-min chunks to fit local LLM context comfortably
LONG_VIDEO_THRESHOLD = 500     # chunk videos longer than ~8 min
CHUNK_OVERLAP_SECONDS = 45
GPT_CALL_TIMEOUT_SECONDS = 300  # cap LLM polls at 5 min — a wedged call should fail fast
MAX_HIGHLIGHT_API_ATTEMPTS = 3


def call_muapi_llm(prompt: str) -> str:
    """Default LLM backend: MuAPI gpt-5-mini."""
    result = muapi.run(
        "gpt-5-mini",
        {"prompt": prompt},
        label="gpt-5-mini",
        timeout=GPT_CALL_TIMEOUT_SECONDS,
    )

    outputs = result.get("outputs")
    if isinstance(outputs, list) and outputs and isinstance(outputs[0], str) and outputs[0].strip():
        return outputs[0]

    for key in ("output", "text", "response", "result", "content"):
        v = result.get(key)
        if isinstance(v, str) and v.strip():
            return v
        if isinstance(v, dict):
            inner = v.get("text") or v.get("content")
            if isinstance(inner, str) and inner.strip():
                return inner
        if isinstance(v, list) and v and isinstance(v[0], str):
            return v[0]

    raise RuntimeError(f"Could not extract gpt-5-mini text from response: {result}")


def _parse_json_loose(raw: str) -> Dict:
    """gpt-5-4 sometimes wraps JSON in markdown fences — strip and parse."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end + 1])
        raise


def _coerce_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


INTRO_REGEX = re.compile(
    r"\b("
    r"chào mừng|chào các bạn|chào quý vị|chào anh chị|chào mọi người|"
    r"quay trở lại với|kênh của mình|kênh youtube|"
    r"đăng ký kênh|subscribe|sub kênh|nhớ like|hãy like|bấm chuông|ấn chuông|"
    r"ủng hộ kênh|theo dõi kênh|chia sẻ video|đừng quên like|đừng quên subscribe|"
    r"welcome back|welcome to|don't forget to subscribe|hit the subscribe|hit the bell|"
    r"like and subscribe|subscribe to my channel|please subscribe|in today's video|today we are|"
    r"before we start|sponsored by"
    r")\b",
    re.IGNORECASE,
)

SENTENCE_END_PUNCTUATION = {".", "?", "!", "…", "...", '"', "'", "”", "’"}


def snap_to_segment_boundaries(
    start_time: float,
    end_time: float,
    segments: List[Dict],
    duration: float = 0.0,
    min_duration: float = 40.0,
    max_duration: float = 65.0,
) -> Tuple[float, float]:
    """Snap candidate clip boundaries to clean speech segment boundaries and skip channel intros.

    Prevents mid-sentence / mid-word cuts and removes generic greetings/subscribe CTAs.
    """
    if not segments:
        max_limit = duration if duration > 0 else float("inf")
        s = max(0.0, start_time)
        e = max(s + min_duration, end_time)
        if max_limit != float("inf"):
            s = min(s, max(0.0, max_limit - 5.0))
            e = min(max_limit, e)
        return (round(s, 2), round(e, 2))

    total_duration = duration if duration > 0 else segments[-1]["end"]

    # 1. Skip early intro / greeting segments if start_time is near video start (< 25s)
    if start_time < 25.0:
        first_content_idx = None
        for i, seg in enumerate(segments):
            if seg["start"] >= 30.0:
                break
            text = seg.get("text", "").strip()
            if not INTRO_REGEX.search(text):
                first_content_idx = i
                break

        if first_content_idx is not None and first_content_idx > 0:
            content_start = segments[first_content_idx]["start"]
            if start_time < content_start:
                print(
                    f"[highlights] Skipped channel intro ({start_time:.1f}s), advancing start to {content_start:.1f}s",
                    flush=True,
                )
                start_time = content_start

    # 2. Snap start_time to segment start
    chosen_start_idx = 0
    min_dist = float("inf")
    search_start = first_content_idx if (start_time < 25.0 and first_content_idx is not None and first_content_idx > 0) else 0

    for i in range(search_start, len(segments)):
        seg = segments[i]
        is_in_seg = (seg["start"] <= start_time < seg["end"]) or (i == len(segments) - 1 and seg["start"] <= start_time <= seg["end"])
        if is_in_seg:
            chosen_start_idx = i
            break
        dist = abs(seg["start"] - start_time)
        if dist < min_dist:
            min_dist = dist
            chosen_start_idx = i

    snapped_start = segments[chosen_start_idx]["start"]

    # 3. Determine target duration bounds
    eff_min_dur = min(min_duration, max(15.0, total_duration - snapped_start))
    eff_max_dur = min(max_duration, max(eff_min_dur, total_duration - snapped_start))

    # 4. Search candidate segments for snapped_end
    candidates = []
    for i in range(chosen_start_idx, len(segments)):
        seg = segments[i]
        dur = seg["end"] - snapped_start
        if dur < eff_min_dur:
            continue
        if dur > eff_max_dur:
            break
        candidates.append((i, seg))

    if not candidates:
        for i in range(chosen_start_idx, len(segments)):
            seg = segments[i]
            dur = seg["end"] - snapped_start
            if dur >= eff_min_dur * 0.75:
                candidates.append((i, seg))
                if dur >= eff_min_dur:
                    break

    if not candidates:
        snapped_end = min(total_duration, segments[-1]["end"])
        if snapped_end <= snapped_start:
            snapped_end = min(total_duration, snapped_start + 60.0)
        return (round(snapped_start, 2), round(snapped_end, 2))

    # 5. Score candidates to pick the cleanest sentence-end
    best_score = -float("inf")
    best_end = candidates[0][1]["end"]

    for idx, seg in candidates:
        dur = seg["end"] - snapped_start
        text = seg.get("text", "").strip()
        score = 0.0

        # Sentence-ending punctuation bonus
        if any(text.endswith(p) for p in SENTENCE_END_PUNCTUATION):
            score += 100.0

        # Speech pause bonus
        if idx + 1 < len(segments):
            pause = segments[idx + 1]["start"] - seg["end"]
            if pause >= 0.35:
                score += 30.0

        # Target duration proximity: prefer 55-60s
        score -= abs(dur - 55.0)

        if score > best_score:
            best_score = score
            best_end = seg["end"]

    snapped_end = min(total_duration, best_end)
    return (round(snapped_start, 2), round(snapped_end, 2))


def _sanitize_highlights(
    raw_highlights: object,
    duration: float,
    segments: Optional[List[Dict]] = None,
) -> List[Dict]:
    """Normalize model output into the expected shape; snap to segment boundaries."""
    if not isinstance(raw_highlights, list):
        return []

    max_end = duration if duration > 0 else float("inf")
    cleaned: List[Dict] = []
    for item in raw_highlights:
        if not isinstance(item, dict):
            continue

        raw_start = _coerce_float(item.get("start_time"), default=-1.0)
        raw_end = _coerce_float(item.get("end_time"), default=-1.0)
        if raw_start < 0 or raw_end <= raw_start:
            continue

        if segments:
            start, end = snap_to_segment_boundaries(
                raw_start,
                raw_end,
                segments,
                duration=duration,
                min_duration=min(40.0, max(15.0, duration * 0.6)) if duration > 0 else 40.0,
                max_duration=min(65.0, duration) if duration > 0 else 65.0,
            )
        else:
            start = raw_start
            end = raw_end
            if end - start < 40.0 and duration > 0:
                end = min(duration, start + 60.0)

        if max_end != float("inf"):
            start = min(start, max_end)
            end = min(end, max_end)
            if end <= start:
                continue

        cleaned.append(
            {
                "title": str(item.get("title") or "Untitled Highlight").strip(),
                "start_time": start,
                "end_time": end,
                "score": max(0, min(100, _coerce_int(item.get("score"), default=0))),
                "hook_sentence": str(item.get("hook_sentence") or "").strip(),
                "virality_reason": str(item.get("virality_reason") or "").strip(),
            }
        )

    return cleaned


def detect_content_type(transcript: Dict, llm_fn: LLMFn = call_muapi_llm) -> Dict[str, str]:
    segments = transcript.get("segments", [])
    sample = " ".join(s["text"] for s in segments[:25])[:3000]
    prompt = f"{CONTENT_TYPE_PROMPT}\n\nTranscript sample:\n{sample}"
    try:
        raw = llm_fn(prompt)
        return _parse_json_loose(raw)
    except Exception:
        return {"content_type": "other", "density": "medium"}


def build_transcript_text(transcript: Dict) -> str:
    segments = transcript.get("segments", [])
    return "\n".join(f"[{s['start']:.1f}s] {s['text'].strip()}" for s in segments)


def chunk_transcript(transcript: Dict) -> List[Dict]:
    segments = transcript.get("segments", [])
    duration = transcript.get("duration", segments[-1]["end"] if segments else 0)
    chunks = []
    start = 0
    while start < duration:
        end = min(start + CHUNK_SIZE_SECONDS, duration)
        chunk_segs = [
            s for s in segments
            if s["start"] >= start and s["end"] <= end + CHUNK_OVERLAP_SECONDS
        ]
        if chunk_segs:
            chunk = dict(transcript)
            chunk["segments"] = chunk_segs
            chunk["duration"] = end - start
            chunk["_offset"] = start
            chunks.append(chunk)
        start += CHUNK_SIZE_SECONDS - CHUNK_OVERLAP_SECONDS
    return chunks


def call_highlight_api(
    transcript_text: str,
    content_info: Dict,
    duration: float,
    num_clips: int,
    is_chunk: bool = False,
    llm_fn: LLMFn = call_muapi_llm,
    segments: Optional[List[Dict]] = None,
) -> Dict:
    if is_chunk:
        num_instruction = "Generate 1 or 2 of the most viral highlights from this section"
    else:
        target = max(num_clips * 2, 5)
        natural_max = max(3, int(duration / 90))
        min_clips = min(target, natural_max, 8)
        num_instruction = f"Generate at least {min_clips} highlights"

    system = HIGHLIGHT_SYSTEM_PROMPT.format(
        virality_criteria=VIRALITY_CRITERIA,
        content_type=content_info.get("content_type", "other"),
        density=content_info.get("density", "medium"),
        num_clips_instruction=num_instruction,
    )
    base_prompt = f"{system}\n\nTranscript:\n{transcript_text}"
    prompt = base_prompt
    last_error = "unknown"

    for attempt in range(1, MAX_HIGHLIGHT_API_ATTEMPTS + 1):
        raw = llm_fn(prompt)
        try:
            parsed = _parse_json_loose(raw)
            raw_h = None
            if isinstance(parsed, list):
                raw_h = parsed
            elif isinstance(parsed, dict):
                raw_h = parsed.get("highlights") or parsed.get("clips") or parsed.get("data") or parsed.get("results")
            highlights = _sanitize_highlights(raw_h, duration=duration, segments=segments)
            if highlights:
                return {"highlights": highlights}
            last_error = f"no valid highlights in response: {raw[:150]}"
        except Exception as e:
            last_error = f"{e} (raw: {raw[:150]})"

        if attempt < MAX_HIGHLIGHT_API_ATTEMPTS:
            print(
                f"[highlights] invalid model output on attempt {attempt}/{MAX_HIGHLIGHT_API_ATTEMPTS}; retrying",
                flush=True,
            )
            prompt = (
                base_prompt
                + "\n\nIMPORTANT: Return ONLY valid JSON with a top-level 'highlights' array."
                + " Each item must include: title, start_time, end_time, score, hook_sentence, virality_reason."
                + " No markdown fences, no commentary."
            )

    raise RuntimeError(
        f"Highlight generator produced invalid output after {MAX_HIGHLIGHT_API_ATTEMPTS} attempts: {last_error}"
    )


def dedupe_highlights(highlights: List[Dict]) -> List[Dict]:
    """Drop a highlight if it overlaps >50% with a higher-scoring one already kept."""
    highlights = sorted(highlights, key=lambda x: int(x.get("score", 0)), reverse=True)
    kept: List[Dict] = []
    for h in highlights:
        h_start = float(h["start_time"])
        h_end = float(h["end_time"])
        h_dur = h_end - h_start
        overlapping = False
        for k in kept:
            latest_start = max(h_start, float(k["start_time"]))
            earliest_end = min(h_end, float(k["end_time"]))
            overlap = earliest_end - latest_start
            if overlap > 0 and overlap > 0.5 * h_dur:
                overlapping = True
                break
        if not overlapping:
            kept.append(h)
    return kept


def get_highlights(
    transcript: Dict,
    num_clips: int = 3,
    llm_fn: Optional[LLMFn] = None,
) -> Dict:
    """Main entry point — returns {highlights: [...]} sorted by score.

    `llm_fn` swaps the underlying LLM. Defaults to MuAPI gpt-5-mini; local
    mode passes in a local LLM-backed callable.
    """
    llm_fn = llm_fn or call_muapi_llm
    duration = transcript.get("duration", 0)
    segments = transcript.get("segments", [])
    content_info = detect_content_type(transcript, llm_fn=llm_fn)
    print(f"[highlights] content={content_info.get('content_type')} density={content_info.get('density')} duration={duration:.0f}s", flush=True)

    if duration >= LONG_VIDEO_THRESHOLD:
        chunks = chunk_transcript(transcript)
        print(f"[highlights] long video — splitting into {len(chunks)} chunks", flush=True)
        all_highlights: List[Dict] = []
        for i, chunk in enumerate(chunks):
            offset = chunk.get("_offset", 0)
            text = build_transcript_text(chunk)
            print(f"[highlights] chunk {i + 1}/{len(chunks)} (offset {offset:.0f}s)", flush=True)
            try:
                result = call_highlight_api(
                    text,
                    content_info,
                    duration,
                    num_clips=num_clips,
                    is_chunk=True,
                    llm_fn=llm_fn,
                    segments=chunk.get("segments"),
                )
                for h in result.get("highlights", []):
                    if float(h["start_time"]) < offset:
                        h["start_time"] = float(h["start_time"]) + offset
                        h["end_time"] = float(h["end_time"]) + offset
                    all_highlights.append(h)
            except Exception as e:
                print(f"[highlights] Warning: chunk {i + 1} failed ({e}); continuing with next chunks...", flush=True)

        if not all_highlights:
            raise RuntimeError("Highlight generator produced zero highlights across all chunks.")
        raw_candidates = all_highlights
    else:
        text = build_transcript_text(transcript)
        result = call_highlight_api(
            text,
            content_info,
            duration,
            num_clips=num_clips,
            llm_fn=llm_fn,
            segments=segments,
        )
        raw_candidates = result.get("highlights", [])

    # Final pass: snap all highlights against full transcript segments and filter intros
    snapped_highlights: List[Dict] = []
    for h in raw_candidates:
        s, e = snap_to_segment_boundaries(
            float(h["start_time"]),
            float(h["end_time"]),
            segments,
            duration=duration,
            min_duration=min(40.0, max(15.0, duration * 0.6)) if duration > 0 else 40.0,
            max_duration=min(65.0, duration) if duration > 0 else 65.0,
        )
        if e > s:
            h["start_time"] = s
            h["end_time"] = e
            snapped_highlights.append(h)

    highlights = dedupe_highlights(snapped_highlights)
    return {"highlights": highlights}
