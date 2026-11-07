"""Build patched (brand-free) canvas assets per NAMING-REGISTRY v1.1.

Protected (functional contracts, NOT renamed in R1):
  - run_qiaodoumay_cli + `qiaodoumay ` CLI display strings (JS<->Rust invoke contract)
  - the two Codex bridge instruction strings (paired with an identical Rust-side
    copy; renaming one side breaks the verbatim-consistency check) -> R2
Everything else with brand tokens gets renamed.
"""
import re, json, sys

SRC = {
    "bundle_live.js": "bundle_yz.js",
    "style_live.css": "style_yz.css",
    "index_live.html": "index_yz.html",
}

PROTECT = [
    # Codex bridge instruction pair (R2: must rename together with Rust copy)
    "\u6211\u7684\u6865\u8c46\u9ebb\u8863\u753b\u5e03\u5df2\u5f00\u542f Codex \u672c\u5730\u6865\u63a5\uff1a",
]

def protect(s):
    for i, p in enumerate(PROTECT):
        s = s.replace(p, "\x00PROT%d\x00" % i)
    return s

def restore(s):
    for i, p in enumerate(PROTECT):
        s = s.replace("\x00PROT%d\x00" % i, p)
    return s

# ordered longest-first
REPL = [
    # entity-encoded brand title in index.html (qiaodoumayijiang -> yaozheng)
    ("&#26725;&#35910;&#40635;&#34915;&#37233;", "&#24186;&#27491;"),
    ("Qiaodoumayijiang", "YaozhengDugui"),
    # R1.3 (human ruling 2026-11-07): yaozhengduigui had one extra "i";
    # correct form is yaozhengdugui
    ("qiaodoumayi", "yaozhengdugui"),
    ("Qiaodoumayi", "YaozhengDugui"),
    ("QIAODOUMAYI", "YAOZHENGDUGUI"),
    # JS-only localStorage keys with the short qiaodoumay_ prefix
    ("qiaodoumay_cli_mode", "yaozhengdugui_cli_mode"),
    ("qiaodoumay_agent_prompt_cache", "yaozhengdugui_agent_prompt_cache"),
    ("qiaodoumay_agent_header_timeout_ms", "yaozhengdugui_agent_header_timeout_ms"),
    ("qiaodoumay_agent_stream_timeout_ms", "yaozhengdugui_agent_stream_timeout_ms"),
    # internal flag
    ("__qdmy_localStorageShortCache_patched__", "__yz_lsShortCachePatched__"),
    # brand short code qdm -> yz (class prefixes, internal identifiers)
    ("qdm", "yz"),
    # display phrases
    # R1.1: top-center brand span (unique "@桥豆麻衣酱" in bundle) -> full brand
    ("@\u6865\u8c46\u9ebb\u8863\u9171", "@\u5e7a\u6b63\u753b\u5e03"),  # @qiaodoumayijiang -> @幺正画布
    # R1.2: topbar display version ONLY (unique `children:"V.3.5.1"` JSX prop;
    # the functional export-format strings `version:"V.3.5.1"` do NOT match
    # this pattern and stay untouched)
    ('children:"V.3.5.1"', 'children:"V.3.8.1"'),
    ("\u6865\u8c46\u9ebb\u8863\u9171", "\u5e7a\u6b63"),          # qiaodoumayijiang -> yaozheng
    ("\u6865\u8c46\u9ebb\u8863\u753b\u5e03", "\u5e7a\u6b63\u753b\u5e03"),  # ..canvas -> yaozheng canvas
    ("\u9ebb\u8863\u753b\u5e03", "\u5e7a\u6b63\u753b\u5e03"),    # mayi canvas -> yaozheng canvas
    ("\u9ebb\u8863", "\u5e7a\u6b63"),                            # remaining mayi -> yaozheng
]

# Startup script injected into index_yz.html:
# 1) sets the NATIVE window title (Tauri title bar comes from tauri.conf.json;
#    document.title does not propagate). __TAURI__ global exists
#    (withGlobalTauri) and plugin:window|set_title is permitted
#    (verified 2026-11-07 via CDP). The bundle never calls setTitle itself.
# 2) reshapes the top-center brand bar into TWO lines:
#    line1 = the 9 existing spans (React-owned, untouched),
#    line2 = contact line, appended as a full-width row (flex-wrap).
#    Re-applied on an interval because React re-renders may wipe the node.
TITLE_SCRIPT = """<script>
(function(){
  var TITLE="\\u5E7A\\u6B63\\u753B\\u5E03";
  var L2="\\u5546\\u52A1DY\\uFF1A\\u9006\\u71B5\\u7684\\u7F8E\\u5B66 https://github.com/kaitoops";
  function setTitle(){try{
    var w=window.__TAURI__&&window.__TAURI__.window;
    if(!w)return false;
    var cur=w.getCurrentWindow?w.getCurrentWindow():(w.getCurrent?w.getCurrent():null);
    if(!cur||!cur.setTitle)return false;
    cur.setTitle(TITLE);
    return true;
  }catch(e){return false}}
  function topbar(){
    var spans=document.getElementsByTagName("span");
    for(var i=0;i<spans.length;i++){
      var t=spans[i].textContent||"";
      if(t.indexOf("@\\u5E7A\\u6B63\\u753B\\u5E03")===0){
        var C=spans[i].parentElement;
        if(!C)continue;
        // R1.3: center the fixed brand bar horizontally in the program frame.
        // The app anchors it with inline left/right computed from a stale
        // layout (~46px off). Measure-free approach: left:50% + translateX
        // (-50%) with right:auto lets the bar shrink-to-fit its content and
        // self-center — no dependence on render timing.
        try{
          C.style.setProperty("left","50%","important");
          C.style.setProperty("right","auto","important");
          var tf=C.style.transform||"";
          if(tf.indexOf("translateX")<0)C.style.setProperty("transform","translateX(-50%)","important");
          C.style.setProperty("margin","0","important");
          // line1 spans are packed at content start inside the bar (bar width
          // is set by the wider line2) -> force flex + center, or line1 sits
          // ~140px left of the frame center. Idempotent if already flex.
          C.style.setProperty("display","flex","important");
          C.style.setProperty("justifyContent","center","important");
        }catch(e){}
        if(C.querySelector("div[data-yz-l2]"))return true;
        C.style.flexWrap="wrap";
        C.style.rowGap="2px";
        var l2=document.createElement("div");
        l2.setAttribute("data-yz-l2","1");
        l2.style.cssText="flex:0 0 100%;text-align:center;font-weight:600;font-size:12px;line-height:1.4;color:#a1a1aa;white-space:nowrap;";
        l2.textContent=L2;
        C.appendChild(l2);
        return true;
      }
    }
    return false;
  }
  var n=0;
  var fast=setInterval(function(){setTitle();topbar();if(++n>60)clearInterval(fast)},500);
  setInterval(function(){topbar()},1000);
})();
</script>
"""

def patch(text):
    n_before = {}
    text = protect(text)
    for old, new in REPL:
        n_before[old] = text.count(old)
        text = text.replace(old, new)
    text = restore(text)
    return text, n_before

summary = {}
for src, dst in SRC.items():
    t = open(src, encoding="utf-8", errors="replace").read()
    t2, counts = patch(t)
    # residual brand scan
    resid = {}
    for p in ["qiaodoumayi", "Qiaodoumayi", "QIAODOUMAYI", "\u6865\u8c46", "\u9ebb\u8863", "qdmy",
              "yaozhengduigui", "YaozhengDuigui", "YAOZHENGDUIGUI"]:
        n = t2.count(p)
        if n:
            resid[p] = n
    open(dst, "w", encoding="utf-8", newline="").write(t2)
    if dst == "index_yz.html":
        t2 = open(dst, encoding="utf-8").read()
        if "</body>" in t2 and TITLE_SCRIPT not in t2:
            t2 = t2.replace("</body>", TITLE_SCRIPT + "</body>", 1)
            open(dst, "w", encoding="utf-8", newline="").write(t2)
            print("index_yz.html: injected native-title startup script")
    summary[dst] = {"replaced": counts, "residual": resid,
                    "len": (len(t), len(t2))}
    print(dst, "replaced:", {k: v for k, v in counts.items() if v},
          "residual:", resid)
json.dump(summary, open("patch_summary.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("protected strings intact:", all(p in open("bundle_yz.js", encoding="utf-8").read() for p in PROTECT))
