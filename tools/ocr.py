"""Local OCR with line bounds; no image contents leave this Mac."""
import csv
import io
import os
from pathlib import Path
import shutil
import struct
import subprocess


def recognize(path, backend="auto"):
    if backend == "auto":
        # Complementary failures: Vision reads blue dialogue well, Tesseract
        # catches small menu labels. Both inspect the same immutable PNG.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(recognize,path,b) for b in ("tesseract","vision","masked")]
            results=[]
            for f in futures:
                try:results.append(f.result())
                except (OSError,subprocess.SubprocessError):pass
        if not results:raise RuntimeError("Both local OCR engines failed")
        data=results[0]
        for e in data['elements']:e['source']=data['source']
        for other in results[1:]:
            for e in other['elements']:
                x,y,w,h=e['bounds']
                overlap=False
                for old in data['elements']:
                    a,b,c,d=old['bounds']
                    iw=max(0,min(x+w,a+c)-max(x,a));ih=max(0,min(y+h,b+d)-max(y,b))
                    if iw*ih>0.45*min(w*h,c*d):
                        overlap=True;break
                if not overlap:
                    e['source']=other['source'];data['elements'].append(e)
        data['source']='hybrid-local-ocr' if len(results)>1 else data['source']
        return data
    exe=shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"
    if backend == "vision" or not Path(exe).exists():
        import json
        helper=Path(__file__).resolve().parents[2]/"work/bin/switch-ocr"
        return json.loads(subprocess.check_output([str(helper),str(path)],timeout=10))
    if backend == "masked":
        helper=Path(__file__).resolve().parents[2]/"work/bin/ocr-mask"
        masked=Path(path).with_suffix(".mask.png")
        subprocess.run([str(helper),str(path),str(masked)],check=True,timeout=5)
        path=masked
    env=dict(os.environ,OMP_THREAD_LIMIT="1")
    result=subprocess.run([exe,str(path),"stdout","--psm","11","tsv"],
                          env=env,capture_output=True,text=True,check=True,timeout=10)
    width,height=struct.unpack(">II",Path(path).read_bytes()[16:24])
    lines={}
    # Tesseract TSV contains literal quotation marks, not CSV quoted fields.
    for row in csv.DictReader(io.StringIO(result.stdout),delimiter="\t",quoting=csv.QUOTE_NONE):
        if row['level']!='5' or not row['text'].strip() or float(row['conf'])<20:continue
        key=tuple(row[k] for k in ('page_num','block_num','par_num','line_num'))
        lines.setdefault(key,[]).append(row)
    elements=[]
    for words in lines.values():
        x=min(int(w['left']) for w in words);y=min(int(w['top']) for w in words)
        r=max(int(w['left'])+int(w['width']) for w in words)
        b=max(int(w['top'])+int(w['height']) for w in words)
        elements.append(dict(text=' '.join(w['text'] for w in words),
                             confidence=sum(float(w['conf']) for w in words)/len(words)/100,
                             bounds=[x,y,r-x,b-y]))
    return dict(source="masked-tesseract-ocr" if backend=="masked" else "tesseract-ocr",width=width,height=height,elements=elements)
