"""Source extraction and OCR run only in GitHub Actions; original raster bytes are preserved."""
import os
os.environ['OMP_NUM_THREADS']='1'
import pathlib,json,hashlib,concurrent.futures,collections
import fitz
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'_site'
for path in [OUT,OUT/'data',OUT/'pdf',OUT/'img',ROOT/'data/ocr',ROOT/'input']:path.mkdir(parents=True,exist_ok=True)
sources=json.loads((ROOT/'tools/sources.json').read_text());engine=None
def dump(path,d):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')))
def ocr_init():
 global engine
 from rapidocr_onnxruntime import RapidOCR
 engine=RapidOCR(intra_op_num_threads=1,inter_op_num_threads=1)
def work(job):
 id,pn=job;doc=fitz.open(ROOT/'input'/f'{id}.pdf');p=doc[pn-1];w,h=p.rect.width,p.rect.height
 folder=OUT/'img'/id;folder.mkdir(exist_ok=True);raw=None
 images=p.get_images()
 if images:
  image=max(images,key=lambda x:x[2]*x[3]);rects=p.get_image_rects(image[0]);r=rects[0] if rects else fitz.Rect()
  if abs(r.width/w-1)<.02 and abs(r.height/h-1)<.02 and abs(r.x0)<3 and abs(r.y0)<3:
   candidate=doc.extract_image(image[0])
   if candidate['ext'] in ['png','jpeg','jpg'] and abs(candidate['width']/candidate['height']-w/h)<.025:raw=candidate
 if raw:
  ext='jpg' if raw['ext']=='jpeg' else raw['ext'];imagebytes=raw['image'];method='embedded-original'
 else:
  pix=p.get_pixmap(dpi=225,alpha=False);ext='png';imagebytes=pix.tobytes('png');method='first-render-225dpi'
 (folder/f'{pn:03}.{ext}').write_bytes(imagebytes)
 cache=ROOT/'data/ocr'/f'{id}-{pn:03}.json'
 if cache.exists():record=json.loads(cache.read_text())
 else:
  lines=[]
  for b in p.get_text('dict')['blocks']:
   for l in b.get('lines',[]):lines.append({'t':''.join(s['text'] for s in l['spans']),'b':list(l['bbox'])})
  ocr=len(''.join(l['t'] for l in lines).strip())<40
  if ocr:
   import numpy as np
   scale=min(2.5,1800/w);pix=p.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False);a=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,3);result,_=engine(a);lines=[]
   for poly,text,score in result or []:
    lines.append({'t':text,'b':[min(z[0] for z in poly)/scale,min(z[1] for z in poly)/scale,max(z[0] for z in poly)/scale,max(z[1] for z in poly)/scale],'confidence':round(float(score),4)})
  lines.sort(key=lambda l:(round(l['b'][1]/4),l['b'][0]));record={'page':pn,'width':w,'height':h,'text':'\n'.join(l['t'] for l in lines),'lines':lines,'ocr':ocr};dump(cache,record)
 record.update(ext=ext,bytes=len(imagebytes),sha256=hashlib.sha256(imagebytes).hexdigest(),imageMethod=method);dump(cache,record);print(id,pn,len(record['text']),method,flush=True);return id,record
if __name__=='__main__':
 jobs=[]
 for s in sources:
  p=ROOT/'input'/f'{s["id"]}.pdf'
  with p.open('wb') as f:
   for part in s['parts']:f.write((ROOT/part).read_bytes())
  assert hashlib.sha256(p.read_bytes()).hexdigest()==s['sha256'];(OUT/'pdf'/p.name).write_bytes(p.read_bytes());s['pageCount']=len(fitz.open(p));jobs.extend((s['id'],n) for n in range(1,s['pageCount']+1))
 records=collections.defaultdict(list)
 with concurrent.futures.ProcessPoolExecutor(max_workers=4,initializer=ocr_init) as ex:
  for id,p in ex.map(work,jobs):records[id].append(p)
 report=[]
 for s in sources:
  ps=sorted(records[s['id']],key=lambda p:p['page']);payload={'source':s,'pages':ps};dump(ROOT/'data'/f'{s["id"]}.json',payload);dump(OUT/'data'/f'{s["id"]}.json',payload);report.append({'id':s['id'],'pages':len(ps),'ocrPages':sum(p['ocr'] for p in ps),'imageBytes':sum(p['bytes'] for p in ps),'imageMethods':dict(collections.Counter(p['imageMethod'] for p in ps)),'sha256':s['sha256']})
 dump(ROOT/'data/audit.json',report);dump(OUT/'data/audit.json',report);print(json.dumps(report),flush=True)
 (OUT/'.nojekyll').touch();(OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><h1>原始资料</h1>'+''.join('<p><a href="pdf/'+s['id']+'.pdf">'+s['name']+'</a></p>' for s in sources))
 import subprocess
 if (ROOT/'tools/parse.py').exists():subprocess.run(['python',str(ROOT/'tools/parse.py')],check=True)
