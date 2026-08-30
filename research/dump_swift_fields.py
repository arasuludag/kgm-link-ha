"""Dump Swift Codable field names from an unstripped Mach-O (the KGM LINK app binary).

This is how the request/response schemas in PROTOCOL.md were recovered — no proxy,
no debugger, no decryption: Swift leaves every struct's field names in the reflection
metadata (`__swift5_fieldmd` + `__swift5_reflstr`).

    python3 research/dump_swift_fields.py                    # every type
    python3 research/dump_swift_fields.py RemoteDoorLockBody # filter by substring

Section offsets below are for app version 1.0.7.4 (arm64). For another build, re-read
them with:  otool -l Ccs | grep -A4 "sectname __swift5_"
"""
import struct, sys, re

PATH = "/Applications/KGM LINK.app/Wrapper/Ccs.app/Ccs"
data = open(PATH, "rb").read()

# vmaddr -> file offset mapping for the three sections we care about
SECS = {
    "typeref": (0x1012e3900, 0x1e1ff, 19806464),
    "reflstr": (0x101301b00, 0x25c45, 19929856),
    "fieldmd": (0x101327748, 0x28dd4, 20084552),
}
# __TEXT slide: addr - offset is constant across TEXT sections
SLIDE = 0x1012e3900 - 19806464

def off(vm):
    return vm - SLIDE

def cstr(o):
    e = data.index(b"\0", o)
    return data[o:e].decode("utf-8", "replace")

def rel(o):
    """relative pointer stored at file offset o -> target file offset"""
    if o < 0 or o + 4 > len(data):
        return None
    v = struct.unpack_from("<i", data, o)[0]
    if v == 0:
        return None
    t = o + v
    if t < 0 or t >= len(data):
        return None
    return t

def typename(o):
    """resolve a mangled type name reference, handling symbolic refs"""
    if o is None:
        return "?"
    b = data[o]
    if b == 0x01:                  # direct symbolic ref -> nominal type descriptor
        desc = rel(o + 1)
        if desc is None:
            return "?"
        # context descriptor: Flags(4) Parent(4) Name(4)
        nm = rel(desc + 8)
        if nm is None:
            return "?"
        try:
            base = cstr(nm)
        except ValueError:
            return "?"
        par = rel(desc + 4)
        chain = [base]
        for _ in range(4):
            if par is None:
                break
            pn = rel(par + 8)
            if pn is None:
                break
            try:
                chain.append(cstr(pn))
            except ValueError:
                break
            par = rel(par + 4)
        return ".".join(reversed(chain))
    if b == 0x02:
        return "<indirect>"
    s = cstr(o)
    # crude demangle: pull the length-prefixed identifiers out
    parts = re.findall(r"(\d+)([A-Za-z_][A-Za-z0-9_]*)", s)
    names = []
    for ln, txt in parts:
        names.append(txt[: int(ln)])
    return ".".join(names) if names else s

start = SECS["fieldmd"][2]
end = start + SECS["fieldmd"][1]

out = {}
o = start
while o + 16 <= end:
    mtn = rel(o)
    kind, recsize, nfields = struct.unpack_from("<HHI", data, o + 8)
    if recsize != 12 or nfields > 512:
        o += 4
        continue
    tn = typename(mtn)
    fields = []
    ro = o + 16
    ok = True
    for i in range(nfields):
        if ro + 12 > end:
            ok = False
            break
        fname_o = rel(ro + 8)
        ftype_o = rel(ro + 4)
        if fname_o is None:
            ok = False
            break
        try:
            fields.append((cstr(fname_o), typename(ftype_o)))
        except ValueError:
            ok = False
            break
        ro += 12
    if ok and tn != "?":
        out.setdefault(tn, []).append(fields)
    o = ro if ok else o + 4

targets = sys.argv[1:] if len(sys.argv) > 1 else []
for tn, variants in sorted(out.items()):
    if targets and not any(t.lower() in tn.lower() for t in targets):
        continue
    for f in variants:
        print(f"=== {tn}")
        for name, ftype in f:
            print(f"      {name}: {ftype}")
