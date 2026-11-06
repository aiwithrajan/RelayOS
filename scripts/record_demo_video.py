"""RelayOS — Automated Production Demo Recording Script
Generates a continuous, broadcast-quality 1080p MP4 recording with synchronized AI voiceover.
Duration: ~2m 34s (under 3 minutes), showcasing both non-compliant $21k offer and compliant $23k counter.
"""
import os
import re
import sys
import time
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "demo_artifacts"
OUTPUT_DIR.mkdir(exist_ok=True)
RAW_VIDEO_DIR = OUTPUT_DIR / "raw_video"
RAW_VIDEO_DIR.mkdir(exist_ok=True)
VOICE_DIR = OUTPUT_DIR / "voiceover"
VOICE_DIR.mkdir(exist_ok=True)

FFMPEG = "/Users/apple/.local/bin/ffmpeg"

SCENES = [
    {
        "id": "scene1_intro",
        "title": "Introduction to RelayOS & God-Mode Control Plane",
        "text": "Welcome to RelayOS, the autonomous enterprise deal closing platform built for the Flip the Switch Hackathon. In traditional enterprise sales, closing a contract takes weeks of manual pricing spreadsheets, security reviews, and DevOps provisioning tickets. RelayOS compresses that entire friction-filled lifecycle into a single autonomous Switch session.",
    },
    {
        "id": "scene2_playbook",
        "title": "Deterministic Pricing Playbook & FastMCP Isolation",
        "text": "At the core of RelayOS is our deterministic Pricing Playbook. Commercial terms are evaluated mathematically against company policies with zero LLM hallucination risk. Through dual-agent FastMCP privilege isolation, code agents are strictly prohibited from touching billing tools, while Deal-Desk enforces strict financial compliance.",
    },
    {
        "id": "scene3_isolation",
        "title": "Initial Ask v1 & Security Isolation Enforcement (AT-1, AT-6)",
        "text": "Here in God-Mode Mission Control, Acme FinTech initially requested twenty thousand dollars at one thousand RPM. Deal-Desk immediately flags this ask: the sixty percent gross margin breaches our seventy-five percent floor. And when an unauthorized agent attempts to invoke billing tools, RelayOS immediately blocks it with an HTTP 403 security denial.",
    },
    {
        "id": "scene4_request_21k",
        "title": "Customer Portal & Non-Compliant $21k Offer (Rule R2 Floor Breach)",
        "text": "Next, let's look at the customer negotiation workflow in the portal at slash t slash acme. The client champion requests custom adjustments, proposing twenty-one thousand dollars at six hundred RPM. RelayOS checks the pricing playbook in real-time. Because twenty-one thousand represents a twelve point five percent discount, it breaches Rule R2's ten percent limit and is flagged for founder review.",
    },
    {
        "id": "scene5_counter_23k",
        "title": "Compliant $23k Counter-Offer & Automated Playbook Approval",
        "text": "To close immediately without waiting for exception approvals, the customer selects the compliant twenty-three thousand dollar counter at six hundred RPM. The Playbook engine calculates a seventy-seven point four percent gross margin, passing all rules R1 through R5. RelayOS auto-approves the proposal on the spot and unlocks direct signature.",
    },
    {
        "id": "scene6_fulfillment",
        "title": "Digital Signature & Zero-Touch Autonomous Fulfillment (AT-7, AT-8)",
        "text": "The moment the customer clicks Accept Proposal, RelayOS triggers instant zero-touch fulfillment. The workflow provisions an isolated tenant with guaranteed six hundred RPM capacity, generates a legally binding dual-signature Order Form PDF, and issues the Stripe electronic invoice.",
    },
    {
        "id": "scene7_conclusion",
        "title": "Closed-Loop Verification in God-Mode & Summary",
        "text": "Returning to God-Mode, we verify the completed loop. Acme FinTech is fully live, the audit trail is cryptographically logged, and deal time dropped from weeks to minutes. RelayOS is verified, compliant, and open source on GitHub. Thank you!",
    },
]


def get_audio_duration(file_path: Path) -> float:
    cmd = [FFMPEG, "-i", str(file_path)]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return 15.0


def generate_and_merge_voiceovers():
    print("🎙️ Generating neural AI voiceovers with edge-tts (ChristopherNeural)...")
    scene_audios = []
    durations = {}

    for s in SCENES:
        out_file = VOICE_DIR / f"{s['id']}.mp3"
        # Always regenerate to ensure synchronization with current text
        cmd = [
            "uvx", "edge-tts",
            "--voice", "en-US-ChristopherNeural",
            "--text", s["text"],
            "--write-media", str(out_file)
        ]
        subprocess.run(cmd, check=True)
        dur = get_audio_duration(out_file)
        durations[s["id"]] = dur
        scene_audios.append(out_file)
        print(f"  ✓ {s['id']}: {dur:.2f}s")

    # Concatenate all 7 voiceovers into one seamless master audio file
    concat_list = VOICE_DIR / "audio_concat.txt"
    with open(concat_list, "w") as f:
        for a in scene_audios:
            f.write(f"file '{a.resolve()}'\n")

    master_audio = OUTPUT_DIR / "master_voiceover.mp3"
    subprocess.run([
        FFMPEG, "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", "-y", str(master_audio)
    ], check=True)

    total_dur = get_audio_duration(master_audio)
    print(f"🔊 Master Voiceover generated: {master_audio} ({total_dur:.2f}s = {int(total_dur//60)}m {int(total_dur%60)}s)")
    return durations, total_dur, master_audio


def reset_deal_state():
    import urllib.request
    try:
        req = urllib.request.Request("http://localhost:8000/api/v1/admin/reset", data=b"", method="POST")
        with urllib.request.urlopen(req) as resp:
            print("🔄 Reset RelayOS state to v1 baseline:", resp.read().decode())
    except Exception as e:
        print("Warning: unable to reset state via API:", e)


def record_continuous_demo(durations, total_dur):
    from playwright.sync_api import sync_playwright

    print(f"🎬 Recording continuous browser demo ({total_dur:.2f}s) at 1920x1080...")
    reset_deal_state()

    raw_dir = RAW_VIDEO_DIR / "continuous"
    # Clean up previous raw files in raw_dir
    if raw_dir.exists():
        for old_webm in raw_dir.glob("*.webm"):
            try:
                old_webm.unlink()
            except Exception:
                pass
    raw_dir.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--font-render-hinting=none", "--enable-font-antialiasing"]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            record_video_dir=str(raw_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        # =====================================================================
        # SCENE 1: INTRO (Target: durations['scene1_intro'])
        # =====================================================================
        scene1_end = time.time() + durations["scene1_intro"]
        print("  ▶ Scene 1: Intro & God-Mode Dashboard...")
        page.goto("http://localhost:8000/god-mode", wait_until="networkidle")
        time.sleep(2.0)
        # Pan across KPI cards
        page.mouse.move(300, 260)
        time.sleep(1.5)
        page.mouse.move(500, 260)
        time.sleep(1.5)
        page.mouse.move(700, 260)
        time.sleep(1.5)
        # Hover over Performance chart curve
        page.mouse.move(400, 480)
        time.sleep(2.0)
        # Smooth scroll to preview deal workflow
        page.evaluate("window.scrollBy({ top: 140, behavior: 'smooth' })")
        time.sleep(3.0)
        rem1 = scene1_end - time.time()
        if rem1 > 0:
            time.sleep(rem1)

        # =====================================================================
        # SCENE 2: PLAYBOOK MODAL (Target: durations['scene2_playbook'])
        # =====================================================================
        scene2_end = time.time() + durations["scene2_playbook"]
        print("  ▶ Scene 2: Playbook Modal & FastMCP Isolation...")
        page.locator("#openPlaybookBtn").click()
        time.sleep(2.5)
        # Scroll modal to show rules R1 to R5
        modal = page.locator("#playbookModal > div")
        modal.evaluate("el => el.scrollBy({ top: 220, behavior: 'smooth' })")
        time.sleep(3.5)
        # Scroll down to show Cost Model formula ($1,000 + $7 x RPM)
        modal.evaluate("el => el.scrollBy({ top: 320, behavior: 'smooth' })")
        time.sleep(4.0)
        # Close modal
        page.locator("#closePlaybookBtn").click()
        time.sleep(2.0)
        rem2 = scene2_end - time.time()
        if rem2 > 0:
            time.sleep(rem2)

        # =====================================================================
        # SCENE 3: SECURITY ISOLATION TEST (Target: durations['scene3_isolation'])
        # =====================================================================
        scene3_end = time.time() + durations["scene3_isolation"]
        print("  ▶ Scene 3: Security Isolation Enforcement (AT-6)...")
        # Scroll to Acme FinTech Deal Card showing failing ask v1
        page.evaluate("window.scrollTo({ top: 280, behavior: 'smooth' })")
        time.sleep(2.0)
        page.mouse.move(800, 430)
        time.sleep(2.0)
        # Click Test Security Isolation (AT-6: @architect Billing Attempt)
        isolation_btn = page.locator("#testIsolationBtn")
        isolation_btn.scroll_into_view_if_needed()
        time.sleep(1.0)
        isolation_btn.click()
        time.sleep(3.0)
        # Scroll terminal into view showing @architect DENIED in red
        terminal = page.locator("#terminalLogBox")
        terminal.scroll_into_view_if_needed()
        time.sleep(4.0)
        rem3 = scene3_end - time.time()
        if rem3 > 0:
            time.sleep(rem3)

        # =====================================================================
        # SCENE 4: CUSTOMER PORTAL & $21k NON-COMPLIANT FLOW (Target: durations['scene4_request_21k'])
        # =====================================================================
        scene4_end = time.time() + durations["scene4_request_21k"]
        print("  ▶ Scene 4: Customer Portal & $21,000 Non-Compliant Request...")
        page.goto("http://localhost:8000/t/acme", wait_until="networkidle")
        time.sleep(2.5)
        page.mouse.move(400, 420)
        time.sleep(1.5)
        # Click Request Changes
        page.locator("#rejectBtn").click()
        time.sleep(2.0)
        # Select $21k (Review Needed) preset chip
        chip21k = page.locator("#chip21k")
        if chip21k.count() > 0:
            chip21k.click()
        else:
            page.locator("#modalPriceInput").fill("21000")
            page.locator("#modalRpmInput").fill("600")
        time.sleep(2.0)
        # Submit to Switch Deal Room
        page.locator("#submitChangeRequestBtn").click()
        time.sleep(3.0)
        # Scroll slightly to show Deal Desk flagged entry in Live Updates
        page.evaluate("window.scrollTo({ top: 380, behavior: 'smooth' })")
        time.sleep(3.5)
        rem4 = scene4_end - time.time()
        if rem4 > 0:
            time.sleep(rem4)

        # =====================================================================
        # SCENE 5: COMPLIANT $23k COUNTER & AUTO-APPROVAL (Target: durations['scene5_counter_23k'])
        # =====================================================================
        scene5_end = time.time() + durations["scene5_counter_23k"]
        print("  ▶ Scene 5: $23,000 Compliant Counter & Auto-Approval...")
        # Scroll back up to click Request Changes for counter
        page.evaluate("window.scrollTo({ top: 80, behavior: 'smooth' })")
        time.sleep(1.5)
        page.locator("#rejectBtn").click()
        time.sleep(2.0)
        # Select $23k Auto-Pass preset chip
        page.locator("#chip23k").click()
        time.sleep(2.0)
        # Submit to Switch Deal Room
        page.locator("#submitChangeRequestBtn").click()
        time.sleep(3.5)
        # Scroll down to show Deal Workflow Stepper advancing to Customer Sign
        page.evaluate("window.scrollTo({ top: 380, behavior: 'smooth' })")
        time.sleep(3.0)
        rem5 = scene5_end - time.time()
        if rem5 > 0:
            time.sleep(rem5)

        # =====================================================================
        # SCENE 6: DIGITAL SIGNATURE & FULFILLMENT (Target: durations['scene6_fulfillment'])
        # =====================================================================
        scene6_end = time.time() + durations["scene6_fulfillment"]
        print("  ▶ Scene 6: Digital Signature & Instant Autonomous Fulfillment...")
        # Scroll up to decision center
        page.evaluate("window.scrollTo({ top: 80, behavior: 'smooth' })")
        time.sleep(1.5)
        # Click Accept Proposal
        page.locator("#acceptBtn").click()
        time.sleep(3.5)
        # Scroll down to watch real-time stepper complete all 5 steps
        page.evaluate("window.scrollTo({ top: 400, behavior: 'smooth' })")
        time.sleep(3.5)
        # Scroll back up to show Download Agreement & Open Live Tenant
        page.evaluate("window.scrollTo({ top: 80, behavior: 'smooth' })")
        time.sleep(2.0)
        page.mouse.move(860, 240)
        time.sleep(2.0)
        rem6 = scene6_end - time.time()
        if rem6 > 0:
            time.sleep(rem6)

        # =====================================================================
        # SCENE 7: CONCLUSION & SUMMARY (Target: durations['scene7_conclusion'])
        # =====================================================================
        scene7_end = time.time() + durations["scene7_conclusion"]
        print("  ▶ Scene 7: Closed-Loop Verification in God-Mode...")
        page.goto("http://localhost:8000/god-mode", wait_until="networkidle")
        time.sleep(2.5)
        # Scroll to completed Acme card
        page.evaluate("window.scrollTo({ top: 220, behavior: 'smooth' })")
        time.sleep(2.5)
        # Scroll to audit logs terminal
        page.evaluate("window.scrollTo({ top: 480, behavior: 'smooth' })")
        time.sleep(2.5)
        # Scroll up to hero banner
        page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
        time.sleep(2.5)
        rem7 = scene7_end - time.time()
        if rem7 > 0:
            time.sleep(rem7)

        context.close()
        browser.close()

    # Find the generated continuous webm file
    webms = list(raw_dir.glob("*.webm"))
    if not webms:
        raise RuntimeError("No raw video webm found in " + str(raw_dir))
    master_webm = OUTPUT_DIR / "master_raw.webm"
    os.replace(webms[0], master_webm)
    print(f"✓ Saved master raw video: {master_webm}")
    return master_webm


def produce_final_master_video(raw_webm, master_audio):
    final_video = BASE_DIR / "relay_os_demo.mp4"
    print(f"🎞️ Merging master video and audio into final 1080p MP4: {final_video}...")

    cmd = [
        FFMPEG,
        "-i", str(raw_webm),
        "-i", str(master_audio),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-y",
        str(final_video),
    ]
    subprocess.run(cmd, check=True)

    # Print summary metrics
    probe = subprocess.run([FFMPEG, "-i", str(final_video)], stderr=subprocess.PIPE, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", probe.stderr)
    dur_str = m.group(0) if m else "Unknown"
    size_mb = os.path.getsize(final_video) / (1024 * 1024)

    print("\n" + "=" * 65)
    print(f"🎉 MASTER DEMO VIDEO GENERATED SUCCESSFULLY!")
    print(f"📁 Path: {final_video}")
    print(f"⏱️ {dur_str}")
    print(f"📦 Size: {size_mb:.2f} MB")
    print(f"🖥️ Resolution: 1920x1080 (Full HD @ 30fps)")
    print(f"🎙️ Audio: Neural AI (Christopher - Reliable & Authoritative)")
    print("=" * 65 + "\n")


def main():
    durations, total_dur, master_audio = generate_and_merge_voiceovers()
    raw_webm = record_continuous_demo(durations, total_dur)
    produce_final_master_video(raw_webm, master_audio)
    reset_deal_state()


if __name__ == "__main__":
    main()
