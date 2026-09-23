from discover_intel.util import url as urlutil


def test_extract_host_basic():
    assert urlutil.extract_host("https://www.nj.com/some/path?x=1") == "www.nj.com"


def test_extract_host_lowercased():
    assert urlutil.extract_host("HTTPS://WWW.NJ.COM/") == "www.nj.com"


def test_extract_host_no_scheme():
    assert urlutil.extract_host("nj.com/path") == "nj.com"


def test_strip_tracking_removes_utm_and_fbclid_and_frag():
    u = "https://x.com/a?utm_source=x&utm_medium=y&fbclid=abc&gclid=zzz&keep=1#frag"
    assert urlutil.strip_tracking(u) == "https://x.com/a?keep=1"


def test_strip_tracking_keeps_query_when_no_junk():
    assert urlutil.strip_tracking("https://x.com/a?id=7") == "https://x.com/a?id=7"


def test_strip_tracking_empty_query_removed():
    assert urlutil.strip_tracking("https://x.com/a?utm_source=x") == "https://x.com/a"
