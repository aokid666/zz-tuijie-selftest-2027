import pathlib,json,hashlib,collections,concurrent.futures
import fitz
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'_site';OUT.mkdir(exist_ok=True);(OUT/'data').mkdir(exist_ok=True);(OUT/'img').mkdir(exist_ok=True);(OUT/'pdf').mkdir(exist_ok=True)
sources=json.loads((ROOT/'tools/sources.json').read_text())
def dump(name,d):
 s=json.dumps(d,ensure_ascii=False,separators=(',',':'));(ROOT/'data'/name).write_text(s);(OUT/'data'/name).write_text(s)
report=[]
for src in sources:
 raw=b''.join((ROOT/p).read_bytes() for p in src['parts']);assert hashlib.sha256(raw).hexdigest()==src['sha256'];doc=fitz.open(stream=raw,filetype='pdf');(OUT/'pdf'/f'{src["id"]}.pdf').write_bytes(raw)
 pages=[]
 for i,p in enumerate(doc,1):
  lines=[]
  for b in p.get_text('dict')['blocks']:
   for l in b.get('lines',[]):
    lines.append({'t':''.join(s['text'] for s in l['spans']),'b':list(l['bbox']),'spans':[{'t':s['text'],'b':list(s['bbox']),'size':s['size'],'color':s['color']} for s in l['spans']]})
  lines.sort(key=lambda l:(round(l['b'][1]/3),l['b'][0]));pages.append({'page':i,'width':p.rect.width,'height':p.rect.height,'text':'\n'.join(l['t'] for l in lines),'lines':lines})
 # Initial pass preserves native text; OCR only selected samples if the PDF is scanned.
 scanned=[p for p in pages if len(p['text'].strip())<40]
 if scanned:
  from rapidocr_onnxruntime import RapidOCR
  import numpy as np
  engine=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2)
  for p in scanned[:8]:
   page=doc[p['page']-1];pix=page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False);a=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,3);result,_=engine(a);lines=[]
   for box,text,score in result or []:
    lines.append({'t':text,'b':[min(z[0] for z in box)/2,min(z[1] for z in box)/2,max(z[0] for z in box)/2,max(z[1] for z in box)/2],'confidence':score})
   lines.sort(key=lambda l:(round(l['b'][1]/4),l['b'][0]));p.update(lines=lines,text='\n'.join(l['t'] for l in lines),ocr=True)
 folder=OUT/'img'/src['id'];folder.mkdir(exist_ok=True)
 for pn in sorted({1,2,3,4,5,6,7,8,len(doc)//2,len(doc)}-{0}):doc[pn-1].get_pixmap(dpi=180,alpha=False).save(folder/f'{pn:03}.png')
 dump(src['id']+'.json',{'source':src,'pages':pages});report.append({'id':src['id'],'pages':len(doc),'nativeTextPages':len(doc)-len(scanned),'scannedPages':len(scanned),'sha256':src['sha256']});print(report[-1],flush=True)
dump('audit.json',report);(OUT/'.nojekyll').touch();(OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>原始资料</title><h1>原始资料与逐页文本</h1>'+''.join('<p><a href="pdf/'+s['id']+'.pdf">'+s['name']+'</a> · <a href="data/'+s['id']+'.json">逐页文本</a></p>' for s in sources))
