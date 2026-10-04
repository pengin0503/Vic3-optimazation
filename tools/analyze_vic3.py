#!/usr/bin/env python3
"""Dependency-free Victoria 3 1.14.x static metadata extractor."""

from __future__ import annotations
import argparse, hashlib, json, re, struct, sys, zipfile
from pathlib import Path

ASCII = re.compile(rb"[\x20-\x7e]{4,}")
UTF16 = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")
SOURCE = re.compile(r"(?i)(?:[A-Za-z]:[\\/])?(?:[A-Za-z0-9_. -]+[\\/])+[A-Za-z0-9_. -]+\.(?:cpp|c|cc|cxx|h|hpp|inl)")
TICK = re.compile(r"CTickTask_[A-Za-z0-9_]+")
COMMANDS = (
    re.compile(r"\bTickTask\.[A-Za-z0-9_.]+\b"),
    re.compile(r"\bThreading\.[A-Za-z0-9_.]+\b"),
    re.compile(r"\bScript(?:\.Profiling|Profiling)[A-Za-z0-9_.]*\b"),
    re.compile(r"\bTools\.GuiDataProfiler\b"),
    re.compile(r"\b(?:clear|dump|log)_ticktask_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgoods_pool_performance_test\b"),
    re.compile(r"\boptick_capture\b"),
)
JOB_TERMS = ("PdxParallel", "NonBlockingJob", "RangeExecution", "TaskScheduler", "GraphJob", "Workset", "TickTask")

class Error(RuntimeError): pass

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def u64(b,o): return struct.unpack_from("<Q",b,o)[0]

class PE:
    def __init__(self,b:bytes):
        self.b=b
        if len(b)<0x40 or b[:2]!=b"MZ": raise Error("not an MZ executable")
        p=u32(b,0x3c)
        if b[p:p+4]!=b"PE\0\0": raise Error("PE signature not found")
        c=p+4
        self.machine=u16(b,c); self.nsec=u16(b,c+2); self.timestamp=u32(b,c+4)
        self.optsz=u16(b,c+16); self.characteristics=u16(b,c+18)
        o=c+20; self.magic=u16(b,o)
        if self.magic!=0x20b: raise Error(f"expected PE32+, got 0x{self.magic:04x}")
        self.linker=f"{b[o+2]}.{b[o+3]}"
        self.entry=u32(b,o+16); self.imagebase=u64(b,o+24)
        self.size_image=u32(b,o+56); self.size_headers=u32(b,o+60)
        self.subsystem=u16(b,o+68); self.dllchars=u16(b,o+70)
        nd=min(u32(b,o+108),16); d=o+112
        self.dirs=[(u32(b,d+i*8),u32(b,d+i*8+4)) for i in range(nd)]
        self.sections=[]; s=o+self.optsz
        for i in range(self.nsec):
            q=s+i*40; name=b[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
            self.sections.append({
                "name":name,"virtual_size":u32(b,q+8),"virtual_address":u32(b,q+12),
                "raw_size":u32(b,q+16),"raw_pointer":u32(b,q+20),
                "characteristics":f"0x{u32(b,q+36):08x}"
            })
    def rva(self,r):
        if r<self.size_headers: return r
        for s in self.sections:
            lo=s["virtual_address"]; hi=lo+max(s["virtual_size"],s["raw_size"])
            if lo<=r<hi:
                off=s["raw_pointer"]+(r-lo)
                if off<len(self.b): return off
        raise Error(f"unmapped RVA 0x{r:x}")
    def cstr(self,r):
        o=self.rva(r); e=self.b.find(b"\0",o,min(len(self.b),o+4096))
        if e<0:e=min(len(self.b),o+4096)
        return self.b[o:e].decode("utf-8","replace")
    def directory(self,i): return self.dirs[i] if i<len(self.dirs) else (0,0)
    def imports(self):
        r,_=self.directory(1)
        if not r:return []
        o=self.rva(r); out=[]
        for i in range(4096):
            q=o+i*20; vals=struct.unpack_from("<IIIII",self.b,q)
            if not any(vals):break
            oft,_,_,name,ft=vals; dll=self.cstr(name); tr=oft or ft; syms=[]
            if tr:
                t=self.rva(tr)
                for j in range(200000):
                    v=u64(self.b,t+j*8)
                    if not v:break
                    if v>>63: syms.append({"ordinal":v&0xffff})
                    else:
                        n=self.rva(v); hint=u16(self.b,n); e=self.b.find(b"\0",n+2,min(len(self.b),n+4096))
                        if e<0:e=min(len(self.b),n+4096)
                        syms.append({"name":self.b[n+2:e].decode("utf-8","replace"),"hint":hint})
            out.append({"dll":dll,"symbols":sorted(syms,key=lambda x:(x.get("name",""),x.get("ordinal",-1)))})
        return sorted(out,key=lambda x:x["dll"].lower())
    def exports(self):
        r,size=self.directory(0)
        if not r:return []
        o=self.rva(r); _,_,_,_,_,base,nfunc,nnames,funcs,names,ords=struct.unpack_from("<IIHHIIIIIII",self.b,o)
        byidx={}
        no=self.rva(names); oo=self.rva(ords)
        for i in range(nnames): byidx[u16(self.b,oo+i*2)]=self.cstr(u32(self.b,no+i*4))
        fo=self.rva(funcs); out=[]
        for i in range(nfunc):
            fr=u32(self.b,fo+i*4)
            if not fr:continue
            x={"ordinal":base+i,"rva":fr}
            if i in byidx:x["name"]=byidx[i]
            if r<=fr<r+size:x["forwarder"]=self.cstr(fr)
            out.append(x)
        return sorted(out,key=lambda x:(x.get("name",""),x["ordinal"]))

def strings(b):
    for m in ASCII.finditer(b): yield m.group().decode("ascii","ignore")
    for m in UTF16.finditer(b): yield m.group()[::2].decode("ascii","ignore")

def read_input(path:Path,target:str):
    if not path.exists():raise Error(f"input path does not exist: {path}")
    if path.is_file() and zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names=[n for n in z.namelist() if not n.startswith("__MACOSX/") and not Path(n).name.startswith("._")]
            req=target.replace("\\","/").lstrip("/")
            hits=[n for n in names if n.rstrip("/")==req.rstrip("/") or n.rstrip("/").endswith("/"+req.rstrip("/"))]
            if not hits and req.lower()=="victoria3.exe": hits=[n for n in names if n.lower().endswith("/binaries/victoria3.exe")]
            if len(hits)!=1:raise Error(f"target {target!r} resolved to {len(hits)} ZIP members")
            return z.read(hits[0]),hits[0]
    if path.is_file():return path.read_bytes(),str(path)
    hits=[p for p in (path/target,path/"binaries"/target) if p.is_file()]
    if not hits:hits=sorted(path.rglob(target))
    if len(hits)!=1:raise Error(f"target {target!r} resolved to {len(hits)} files")
    return hits[0].read_bytes(),str(hits[0])

def analyze(b:bytes,logical:str):
    pe=PE(b); ss=list(strings(b))
    src=set()
    for s in ss:
        for m in SOURCE.finditer(s):
            v=m.group().replace("\\","/").strip(" .,:;()[]{}'\"")
            if ".com/" not in v.lower(): src.add(v)
    cmds=set()
    for s in ss:
        for p in COMMANDS:cmds.update(m.group() for m in p.finditer(s))
    jobs=sorted({s for s in ss if len(s)<=512 and any(k.lower() in s.lower() for k in JOB_TERMS)})
    pdb=[]
    pos=0
    while True:
        pos=b.find(b"RSDS",pos)
        if pos<0:break
        a=pos+24;e=b.find(b"\0",a,min(len(b),a+4096))
        if e>a:
            v=b[a:e].decode("utf-8","ignore")
            if v.lower().endswith(".pdb"):pdb.append(v)
        pos+=4
    return {
      "logical_path":logical,"size_bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),
      "pe":{"kind":"PE32+","machine":f"0x{pe.machine:04x}","timestamp_unix":pe.timestamp,
            "linker_version":pe.linker,"entry_point_rva":f"0x{pe.entry:x}","image_base":f"0x{pe.imagebase:x}",
            "size_of_image":pe.size_image,"subsystem":pe.subsystem,"dll_characteristics":f"0x{pe.dllchars:04x}",
            "sections":pe.sections},
      "pdb_paths":sorted(set(pdb)),"imports":pe.imports(),"exports":pe.exports(),
      "source_paths":sorted(src,key=str.lower),
      "ticktasks":sorted(set(TICK.findall("\n".join(ss)))),
      "rtti_and_job_strings":jobs,
      "profiler_and_console_commands":sorted(cmds)
    }

# Stable names used by tests and future callers.
read_target = read_input
analyze_executable = analyze

def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("input",type=Path);ap.add_argument("--target",default="victoria3.exe");ap.add_argument("--output",type=Path)
    a=ap.parse_args(argv)
    try:b,logical=read_input(a.input,a.target); result={"format_version":1,"executable":analyze(b,logical)}
    except (Error,OSError,zipfile.BadZipFile,struct.error) as e:
        print(f"error: {e}",file=sys.stderr);return 2
    text=json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n"
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text,encoding="utf-8")
    else:sys.stdout.write(text)
    return 0

if __name__=="__main__":raise SystemExit(main())
