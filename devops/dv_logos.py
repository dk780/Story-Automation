"""Real tool / company logos for the explanations. Sources, in order: Iconify SVG logos (rasterised), the site's own icon (PNG),
and finally a clean colour badge with the name, so a logo can never break a video."""
import io, re
from pathlib import Path
import requests
from PIL import Image, ImageDraw
import dv_fonts as F

CACHE = Path("work/devops/_logos")
# name: (Iconify 'logos' id, website for the icon fallback, brand colour for the badge)
REG = {
    "git": ("git-icon", "git-scm.com", (240, 80, 50)), "github": ("github-icon", "github.com", (36, 41, 47)),
    "gitlab": ("gitlab", "gitlab.com", (252, 109, 38)), "docker": ("docker-icon", "docker.com", (36, 150, 237)),
    "kubernetes": ("kubernetes", "kubernetes.io", (50, 109, 230)), "jenkins": ("jenkins", "jenkins.io", (210, 36, 31)),
    "terraform": ("terraform-icon", "terraform.io", (123, 66, 188)), "ansible": ("ansible", "ansible.com", (238, 0, 0)),
    "azure devops": ("azure-devops", "dev.azure.com", (0, 120, 212)), "azure": ("microsoft-azure", "azure.microsoft.com", (0, 120, 212)),
    "aws": ("aws", "aws.amazon.com", (255, 153, 0)), "google cloud": ("google-cloud", "cloud.google.com", (66, 133, 244)),
    "prometheus": ("prometheus", "prometheus.io", (230, 82, 44)), "grafana": ("grafana", "grafana.com", (244, 104, 0)),
    "elasticsearch": ("elasticsearch", "elastic.co", (0, 150, 140)), "kibana": ("kibana", "elastic.co", (240, 78, 152)),
    "logstash": ("logstash", "elastic.co", (230, 170, 0)), "helm": ("helm", "helm.sh", (15, 22, 137)),
    "argo": ("argo-icon", "argoproj.github.io", (239, 123, 77)), "maven": ("maven", "maven.apache.org", (199, 32, 54)),
    "gradle": ("gradle", "gradle.org", (2, 48, 59)), "npm": ("npm-icon", "npmjs.com", (203, 56, 55)),
    "selenium": ("selenium", "selenium.dev", (67, 176, 41)), "sonarqube": ("sonarqube", "sonarsource.com", (78, 154, 205)),
    "nexus": ("sonatype", "sonatype.com", (27, 152, 89)), "linux": ("linux-tux", "kernel.org", (40, 40, 40)),
    "ubuntu": ("ubuntu", "ubuntu.com", (233, 84, 32)), "bash": ("bash-icon", "gnu.org", (60, 60, 60)),
    "python": ("python", "python.org", (53, 114, 165)), "nginx": ("nginx", "nginx.com", (0, 150, 57)),
    "redis": ("redis", "redis.io", (220, 56, 44)), "postgresql": ("postgresql", "postgresql.org", (51, 103, 145)),
    "mongodb": ("mongodb-icon", "mongodb.com", (71, 162, 72)), "vault": ("vault-icon", "vaultproject.io", (30, 30, 30)),
    "datadog": ("datadog", "datadoghq.com", (99, 44, 166)), "slack": ("slack-icon", "slack.com", (74, 21, 75)),
    "jira": ("jira", "atlassian.com", (0, 82, 204)), "kafka": ("kafka-icon", "kafka.apache.org", (35, 31, 32)),
    "puppet": ("puppet-icon", "puppet.com", (255, 174, 26)), "chef": ("chef-icon", "chef.io", (240, 131, 0)),
    "nagios": (None, "nagios.com", (30, 30, 30)), "amazon": ("amazon", "amazon.com", (255, 153, 0)),
    "netflix": ("netflix", "netflix.com", (229, 9, 20)), "walmart": ("walmart", "walmart.com", (0, 113, 206)),
    "facebook": ("facebook", "facebook.com", (24, 119, 242)), "meta": ("meta-icon", "meta.com", (0, 100, 224)),
    "adobe": ("adobe", "adobe.com", (250, 15, 0)), "microsoft": ("microsoft-icon", "microsoft.com", (0, 120, 212)),
    "google": ("google-icon", "google.com", (66, 133, 244)), "etsy": ("etsy", "etsy.com", (241, 100, 30)),
    "spotify": ("spotify-icon", "spotify.com", (30, 215, 96)), "uber": ("uber", "uber.com", (30, 30, 30)),
    "amazon web services": ("aws", "aws.amazon.com", (255, 153, 0)), "linkedin": ("linkedin-icon", "linkedin.com", (10, 102, 194)), "flux": (None, "fluxcd.io", (50, 110, 220)),
}
PALETTE = [(0, 165, 168), (245, 138, 60), (47, 111, 219), (46, 173, 107), (123, 66, 188), (224, 74, 74)]
_mem, _net_fail = {}, [0]


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "logo"


def lookup(name):
    k = re.sub(r"\s+", " ", name.lower().replace("logo", "")).strip()
    if k in REG:
        return REG[k]
    hits = [r for r in REG if r in k]
    if hits:
        return REG[max(hits, key=len)]
    return (slug(name), None, PALETTE[sum(map(ord, name)) % len(PALETTE)])


def _trim(img):
    bb = img.getbbox()
    return img.crop(bb) if bb else None


def _from_svg(svg):
    for fn in (_svg_fitz, _svg_cairo):
        try:
            im = fn(svg)
            im = _trim(im) if im else None
            if im and im.size[0] > 12:
                return im
        except Exception:
            continue
    return None


def _svg_fitz(svg):
    import fitz   # PyMuPDF
    doc = fitz.open(stream=svg, filetype="svg")
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(1.0, 1.0), alpha=True)
    return Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)


def _svg_cairo(svg):
    import cairosvg
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg, output_height=256))).convert("RGBA")


def _get(url, **kw):
    if _net_fail[0] >= 3:
        return None
    try:
        r = requests.get(url, timeout=12, **kw)
        _net_fail[0] = 0
        return r if r.status_code == 200 and len(r.content) > 200 else None
    except Exception:
        _net_fail[0] += 1
        return None


def badge(name, color, px=256):
    img = Image.new("RGBA", (px * 2, px * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, px * 2 - 1, px * 2 - 1], radius=px // 2, fill=tuple(color) + (255,))
    words = name.strip().split()
    lines = [name.strip()] if (len(name) <= 9 or len(words) < 2) else [" ".join(words[:len(words) // 2 or 1]), " ".join(words[len(words) // 2 or 1:])]
    size = px
    while size > 20:
        f = F.font("sans", size)
        if max(f.getlength(l) for l in lines) <= px * 2 * 0.82 and (sum(f.getmetrics()) * len(lines)) <= px * 2 * 0.7:
            break
        size -= 6
    f = F.font("sans", size)
    lh = sum(f.getmetrics())
    y = (px * 2 - lh * len(lines)) / 2
    for l in lines:
        d.text(((px * 2 - f.getlength(l)) / 2, y), l, font=f, fill=(255, 255, 255, 255))
        y += lh
    return img.resize((px, px), Image.LANCZOS)


def get(name):
    """RGBA image of the logo for `name` (never fails)."""
    key = slug(name)
    if key in _mem:
        return _mem[key]
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{key}.png"
    if cached.exists():
        _mem[key] = Image.open(cached).convert("RGBA")
        return _mem[key]
    icon_id, domain, color = lookup(name)
    img = None
    if icon_id:
        r = _get(f"https://api.iconify.design/logos/{icon_id}.svg", params={"height": 256})
        if r is not None:
            img = _from_svg(r.content)
    if img is None and domain:
        r = _get("https://www.google.com/s2/favicons", params={"domain": domain, "sz": 128})
        if r is not None:
            try:
                im = _trim(Image.open(io.BytesIO(r.content)).convert("RGBA"))
                img = im if im and im.size[0] >= 24 else None
            except Exception:
                img = None
    src = "logo" if img is not None else "badge"
    if img is None:
        img = badge(name, color)
    print(f"  logo for {name!r}: {src}")
    try:
        img.save(cached)
    except Exception:
        pass
    _mem[key] = img
    return img
