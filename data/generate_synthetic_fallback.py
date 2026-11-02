"""
FALLBACK ONLY — this generates a synthetic golden set (questions written by
an AI, not sourced from a real dataset). Use data/download_real_dataset.py
instead, which pulls the real Rowden/CybersecurityQAA dataset from Hugging
Face — expert-reviewed, published, and citable. Only fall back to this if
you genuinely can't get network access to Hugging Face and need something
to test the harness plumbing against.

Run:  python3 data/generate_synthetic_fallback.py
"""
import json
import random
import itertools
from pathlib import Path

random.seed(7)

OUT = Path(__file__).parent / "golden_set.jsonl"

# Each category: list of (question_template, must_mention_points)
# Templates use {subject} / {service} / {detail} placeholders for variety.
BANK = ["my bank", "PayPal", "my Chase account", "my crypto exchange account", "my university portal"]
SERVICE = ["Instagram", "Gmail", "my company email", "Netflix", "Steam", "my school Wi-Fi", "Slack", "my router admin panel"]
APP = ["a QR code at a cafe", "a USB stick I found in the parking lot", "a browser extension", "a free VPN app", "a game mod", "a PDF attachment"]

ITEMS = {
    "Phishing": [
        ("I clicked a suspicious link in an email claiming to be from my bank. What should I do?",
         ["disconnect/stop entering info", "change passwords from a clean device", "enable MFA", "monitor accounts", "report the email"]),
        ("I got an SMS saying my package is held and asking me to pay a small fee via a link. Is this safe?",
         ["identify as smishing", "don't click/pay", "verify via official courier site", "report/block the number"]),
        ("An email says my account will be deleted unless I verify within 24 hours. Real or fake?",
         ["urgency is a red flag", "check sender domain", "don't click, go to site directly", "verify via official support"]),
        ("How can I tell if a link in an email is actually going where it says it goes?",
         ["hover to preview URL", "check domain spelling", "use link-expander for shortened URLs", "don't rely on display text alone"]),
        ("I replied to a phishing email with my password before realizing. What now?",
         ["change password immediately", "enable MFA", "check for unauthorized activity", "report to IT/provider"]),
        ("I received an email from my 'boss' asking me to urgently buy gift cards and send the codes. What should I do?",
         ["recognize as CEO fraud/BEC", "verify via a separate known channel", "don't purchase or send codes", "report to security team"]),
        ("A pop-up says my computer is infected and gives a phone number to call for 'Microsoft support'. Should I call?",
         ["identify as tech support scam", "don't call the number", "close the browser/tab safely", "never grant remote access to unknown callers"]),
        ("How do phishing emails try to create a sense of urgency, and why does that work?",
         ["urgency bypasses careful thinking", "common tactics: threats, deadlines, prizes", "slow down and verify independently", "legitimate orgs rarely demand instant action"]),
        ("I got an email that looks exactly like it's from PayPal, logo and all. Does that mean it's real?",
         ["visual branding is easy to fake", "check actual sender email address", "check link destination not just display text", "log in directly via official site instead"]),
        ("What's 'spear phishing' and how is it different from regular phishing?",
         ["targeted at a specific person/org", "uses personal details to seem credible", "harder to detect than generic phishing", "still verify requests independently"]),
        ("Someone emailed me an invoice for a service I never ordered, with a link to 'dispute' it. What should I do?",
         ["treat as phishing attempt", "don't click the dispute link", "verify directly with the claimed company", "delete/report the email"]),
        ("I got a phishing email that even referenced my real order number. How did they know that?",
         ["possible data breach exposed order info", "check if related account was breached", "still don't trust the email's links", "report to the retailer"]),
        ("My coworker forwarded me a suspicious email and asked if it's phishing. What should I look for?",
         ["mismatched sender domain", "urgent/threatening language", "unexpected attachments or links", "generic greeting instead of your name"]),
        ("An email claims I won a prize from a company I've never interacted with. Is this a scam?",
         ["almost certainly phishing/scam", "don't click or provide personal info", "delete or report", "legitimate prizes don't require info upfront"]),
        ("What should a company do to reduce successful phishing attacks against employees?",
         ["regular phishing-simulation training", "email filtering/authentication (SPF/DKIM/DMARC)", "clear reporting process for suspicious emails", "enforce MFA so stolen passwords alone aren't enough"]),
    ],
    "Malware": [
        ("My laptop fan is loud, browser has new toolbars, and ads pop up constantly. Am I infected?",
         ["likely adware/malware", "run reputable antivirus scan", "uninstall unknown extensions/programs", "update OS and browser"]),
        ("I installed a free video converter yesterday and now my computer is acting strange. What should I check?",
         ["uninstall the suspicious software", "run a malware scan", "check startup programs", "consider backup + reinstall if severe"]),
        ("Is it safe to open an .exe file someone sent me on Discord?",
         ["do not run unknown executables", "scan with antivirus first", "verify sender identity", "prefer sandboxed/VM testing"]),
        ("What's the difference between a virus, worm, and trojan, and why does it matter for how I respond?",
         ["virus needs a host file/spreads via execution", "worm self-replicates over network", "trojan disguises as legitimate software", "response steps differ (isolate vs patch vs remove app)"]),
        ("My antivirus flagged a file as malicious but I think it's a false positive. What should I do?",
         ["don't ignore automatically", "check file hash against VirusTotal", "verify source/publisher", "when unsure, quarantine rather than restore"]),
        ("What is a keylogger and how would I know if one is on my device?",
         ["records keystrokes to steal credentials", "signs: unexpected lag, unknown processes", "run anti-malware scan", "change passwords from a clean device after removal"]),
        ("Is it dangerous to download pirated software or games?",
         ["common vector for bundled malware", "no security updates for pirated software", "use official sources/legit alternatives instead", "scan downloads even from familiar-seeming sites"]),
        ("What's the safest way to test a file I'm not sure about without risking my main computer?",
         ["use a sandbox or virtual machine", "upload hash/file to a scanning service", "avoid opening macros in office documents", "isolate from network if testing"]),
        ("My phone is draining battery fast and showing ads even outside apps. Could this be malware?",
         ["possible mobile adware/malware", "review recently installed apps", "check app permissions", "use a reputable mobile security scanner"]),
        ("What are macros in Word/Excel files, and why do security teams warn about them?",
         ["macros can run malicious code automatically", "common malware delivery method via email attachments", "keep macros disabled by default", "only enable for trusted, verified documents"]),
        ("I clicked 'Allow' on a browser notification prompt from a sketchy site. Is that dangerous?",
         ["can lead to spammy/malicious notifications", "review and revoke site notification permissions", "avoid granting permissions to unfamiliar sites", "not usually full system compromise but still risky"]),
        ("What is a 'drive-by download' and how do I avoid it?",
         ["malware downloads just from visiting a compromised page", "keep browser and plugins updated", "use ad-blockers/script blockers cautiously", "avoid disreputable sites"]),
    ],
    "Ransomware": [
        ("My files got encrypted and there's a ransom note demanding payment. What should I do first?",
         ["disconnect from network immediately", "don't pay (not guaranteed to help)", "identify the strain if possible", "restore from backup", "report to authorities"]),
        ("Should I ever pay a ransomware demand to get my files back?",
         ["generally discouraged", "no guarantee of decryption", "may fund further crime", "report to law enforcement, check nomoreransom.org"]),
        ("How can a small business protect itself from ransomware before it happens?",
         ["regular offline/immutable backups", "patch systems promptly", "employee phishing training", "network segmentation", "endpoint detection tools"]),
        ("Ransomware hit one computer on our office network. How do we stop it spreading?",
         ["isolate the infected machine immediately", "disable shared drives/network access", "check other machines for signs", "involve IT/security professionals"]),
        ("What's the difference between a backup that protects against ransomware and one that doesn't?",
         ["offline/air-gapped or immutable backups are protected", "backups constantly connected/synced can get encrypted too", "test restores periodically", "keep multiple backup generations"]),
        ("How do most ransomware infections actually get in?",
         ["phishing emails with malicious attachments/links", "unpatched vulnerable software/RDP exposure", "compromised credentials", "malicious downloads"]),
        ("Is there any way to decrypt files without paying, after a ransomware attack?",
         ["check nomoreransom.org for known decryptors", "not always possible depending on strain", "restore from backup is most reliable", "consult incident response professionals"]),
    ],
    "Password Security": [
        ("Is it safe to reuse my email password on other sites?",
         ["no, enables credential stuffing", "use unique passwords per site", "recommend password manager", "breach on one site compromises others"]),
        ("What makes a strong password in 2026, and do I need special characters?",
         ["length matters more than complexity", "use passphrases", "avoid personal info/dictionary words", "unique per account", "consider passkeys where available"]),
        ("Should I write my passwords down on paper?",
         ["better than reuse, but password manager preferred", "if written, store securely, not near device", "never store in plain text file on computer"]),
        ("How often should I change my passwords?",
         ["not on a fixed schedule if unique+strong", "change immediately if breach suspected", "frequent forced changes can backfire (weaker passwords)"]),
        ("Is a password manager actually safe to use?",
         ["yes, generally safer than reuse/memory", "use reputable, audited manager", "protect master password well + MFA", "understand it's a single point of failure"]),
        ("How do I check if any of my passwords have been leaked in a data breach?",
         ["use breach-checking services like Have I Been Pwned", "change any password found in a breach", "check for reused passwords across accounts", "enable MFA regardless"]),
        ("What's the risk of using a simple, memorable password like a pet's name and birth year?",
         ["easily guessable/crackable", "vulnerable to social-engineering guesses", "use longer random passphrase instead", "avoid public personal info in passwords"]),
        ("Are passkeys more secure than passwords, and should I switch?",
         ["passkeys resistant to phishing (no shared secret)", "based on public-key cryptography tied to device", "worth adopting where supported", "still keep account recovery options secure"]),
        ("My browser offered to save my password. Is that a good idea?",
         ["reasonably safe if device/OS account is secured", "less safe on shared computers", "dedicated password manager offers more features/security", "ensure device lock screen is enabled"]),
    ],
    "MFA": [
        ("Should I use SMS or an authenticator app for two-factor authentication?",
         ["SMS vulnerable to SIM-swapping", "authenticator app/hardware key more secure", "either is better than no MFA", "recommend app or hardware key when available"]),
        ("I lost my phone with my authenticator app on it. How do I get back into my accounts?",
         ["use backup codes saved at setup", "account recovery process via provider", "re-enroll a new device", "revoke old device access once recovered"]),
        ("What is a hardware security key and is it worth buying?",
         ["physical device (e.g., YubiKey) for MFA", "resistant to phishing/remote attacks", "worth it for high-value accounts", "keep a backup key"]),
        ("Is enabling MFA enough to make my account fully safe?",
         ["MFA greatly reduces risk but isn't total protection", "phishing-resistant methods (hardware keys) stronger than OTP", "still need strong unique password + vigilance"]),
        ("I got an MFA push notification I didn't request. What does that mean and what should I do?",
         ["sign someone else has your password", "deny the request", "change password immediately", "check account for suspicious activity"]),
        ("What is 'MFA fatigue' and how do attackers exploit it?",
         ["attacker spams push notifications hoping user approves by accident", "never approve unrecognized prompts", "use number-matching MFA if available", "report repeated unexpected prompts"]),
        ("Why do security experts say SMS-based 2FA is 'better than nothing but not great'?",
         ["vulnerable to SIM-swap and SS7 attacks", "still blocks many basic credential-stuffing attacks", "app/hardware-based MFA preferred where available", "use SMS only if no stronger option exists"]),
    ],
    "Suspicious Links": [
        ("How do I check a shortened URL (like bit.ly) before clicking it?",
         ["use a URL expander/preview tool", "check destination domain", "verify sender legitimacy first", "avoid clicking if unsure"]),
        ("I scanned a QR code at a cafe table and it opened a website asking for my login. Should I enter it?",
         ["treat as suspicious", "don't enter credentials on unknown page", "verify official site independently", "report if phishing"]),
        ("A friend's social media sent me a weird link with no message. Should I click it?",
         ["account may be compromised", "verify with friend through another channel", "don't click without confirmation", "warn friend if compromised"]),
        ("What's the difference between HTTP and HTTPS, and does a padlock icon mean a site is safe?",
         ["HTTPS encrypts traffic", "padlock means encrypted connection, not that content is trustworthy", "phishing sites can also use HTTPS", "check domain, not just padlock"]),
        ("How can I tell if a website domain is a lookalike/typosquat of a real company?",
         ["check for subtle misspellings/extra characters", "verify by typing the known URL directly instead of clicking", "check domain registration age if suspicious", "use official bookmarks for sensitive sites"]),
        ("Are QR codes in public places generally safe to scan?",
         ["can be overlaid with malicious codes by attackers", "preview URL before opening if possible", "be cautious with codes on flyers/stickers in public", "avoid entering sensitive info after scanning unknown codes"]),
        ("I got a link in a text that redirected through 3 different URLs before landing on a page. Is that normal?",
         ["multiple redirects can be used to evade filters/hide destination", "treat as a red flag", "don't enter any information", "report/block sender"]),
    ],
    "Social Engineering": [
        ("Someone called claiming to be IT support asking for my password to 'fix an issue'. What should I do?",
         ["legitimate IT never asks for password", "hang up and verify via official number", "report the attempt", "don't share credentials over phone"]),
        ("A new 'coworker' on Slack is asking me to buy gift cards urgently for the CEO. Is this legitimate?",
         ["classic gift card / CEO fraud scam", "verify identity through separate channel", "urgency + secrecy are red flags", "report to security team"]),
        ("What is 'pretexting' and how do I recognize it?",
         ["attacker creates a fabricated scenario/identity", "often impersonates authority or trusted party", "verify identity independently", "be cautious of unsolicited requests for info"]),
        ("Someone I matched with online is asking detailed personal and financial questions early on. Red flag?",
         ["possible romance scam pattern", "avoid sharing financial details", "be wary of never meeting in person + urgency", "verify identity, consider reporting"]),
        ("What is 'tailgating' in physical security and how do I prevent it at my office?",
         ["unauthorized person follows someone through a secure door", "politely ask to badge in separately", "don't hold doors for unrecognized people in secure areas", "report suspicious entry attempts"]),
        ("A caller claims to be from tech support and asks me to install remote-access software. Should I comply?",
         ["classic tech support scam pattern", "don't install remote access software for unsolicited callers", "hang up and verify independently", "never grant control of your device to unknown callers"]),
        ("What is 'shoulder surfing' and how can I protect myself in public places?",
         ["someone visually observing your screen/PIN entry", "use privacy screens in public", "shield PIN pad when entering codes", "be aware of surroundings when handling sensitive info"]),
    ],
    "Network Security": [
        ("Is it safe to do online banking on public Wi-Fi at a coffee shop?",
         ["risky due to potential eavesdropping/rogue APs", "use VPN if necessary", "prefer cellular data or trusted network", "ensure HTTPS at minimum"]),
        ("How do I secure my home Wi-Fi router?",
         ["change default admin password", "use WPA3/WPA2 encryption", "update firmware regularly", "disable remote management if unused", "use strong unique Wi-Fi password"]),
        ("What is a VPN and does it make me anonymous online?",
         ["encrypts traffic between device and VPN server", "not full anonymity (VPN provider can see traffic)", "protects on untrusted networks", "choose reputable no-log provider"]),
        ("Should I enable remote desktop access on my work computer for convenience?",
         ["increases attack surface if exposed to internet", "use VPN + MFA if needed", "keep patched and restrict access", "disable when not in use"]),
        ("What's the risk of using the same Wi-Fi password for years without changing it?",
         ["increases exposure if password leaked/guessed", "recommend periodic rotation", "check for unknown connected devices", "use WPA3 and strong passphrase"]),
        ("What is a 'rogue access point' and how could it affect me at a public place?",
         ["fake Wi-Fi network mimicking a legitimate one", "attacker can intercept traffic on it", "verify network name with staff before connecting", "avoid sensitive logins on unverified networks"]),
        ("Should I disable my home network's guest Wi-Fi feature?",
         ["guest network isolates visitors from main devices, generally good to keep", "ensure guest network has its own strong password", "disable if unused to reduce attack surface", "keep firmware updated regardless"]),
        ("What does a firewall actually do, and do I need one if I already have antivirus?",
         ["firewall controls network traffic in/out", "antivirus scans for malicious files, different layer", "both provide complementary protection", "most OS have a built-in firewall, keep it enabled"]),
        ("Is it risky to leave Bluetooth or Wi-Fi discoverable mode on all the time?",
         ["can expose device to nearby attackers", "turn off when not needed", "keep device firmware/OS updated", "avoid pairing with unknown devices"]),
    ],
}


# Natural re-framings used to generate paraphrase variants of each base
# question, so the golden set has real linguistic variety instead of one
# phrasing per scenario (useful for testing whether the system/judge are
# robust to how a question is asked, not just what it's about).
WRAPPERS = [
    lambda q: q,
    lambda q: f"Someone I know asked me: \"{q}\" How should I answer them?",
    lambda q: f"{q} I'm not very technical, so please keep it simple.",
    lambda q: f"Quick question — {q[0].lower() + q[1:]}",
]


def build():
    rows = []
    counter = 1
    cats = list(ITEMS.keys())

    # Every base question gets its original phrasing plus paraphrase variants,
    # rotated deterministically so categories stay balanced.
    for cat in cats:
        for template, must_mention in ITEMS[cat]:
            for wrapper in WRAPPERS:
                q = wrapper(template)
                rows.append({
                    "id": f"CS-{counter:03d}",
                    "category": cat,
                    "question": q,
                    "must_mention": must_mention,
                })
                counter += 1

    # dedupe identical questions, keep order
    seen = set()
    unique_rows = []
    for r in rows:
        key = r["question"]
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(r)

    # cap each category at PER_CATEGORY items so the set stays balanced
    # instead of over-represented categories (more base templates -> more
    # paraphrase variants) drowning out the rest.
    PER_CATEGORY = 20
    by_cat = {}
    for r in unique_rows:
        by_cat.setdefault(r["category"], []).append(r)
    for cat in by_cat:
        random.shuffle(by_cat[cat])
    balanced = []
    for cat in cats:
        balanced.extend(by_cat[cat][:PER_CATEGORY])
    random.shuffle(balanced)
    unique_rows = balanced

    # renumber ids after balancing/shuffle
    for i, r in enumerate(unique_rows, start=1):
        r["id"] = f"CS-{i:03d}"

    with OUT.open("w") as f:
        for r in unique_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Wrote {len(unique_rows)} items to {OUT}")
    from collections import Counter
    print("Per-category counts:", dict(Counter(r["category"] for r in unique_rows)))


if __name__ == "__main__":
    build()
