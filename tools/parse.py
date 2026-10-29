"""Original fill-in questions: retain blank source images; verify against the supplied handbook."""
import pathlib,json,re,collections,urllib.request,difflib,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1];BASE='https://aokid666.github.io/zz-tuijie-selftest-2027/';MBASE='https://aokid666.github.io/zz-tuijie-manual-2027/';ID='tuijie-selftest'
def norm(t):return re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]','',t)
def dump(name,d):
 text=json.dumps(d,ensure_ascii=False,separators=(',',':'));(ROOT/'data'/name).write_text(text);(ROOT/'_site/data'/name).write_text(text)
def read_manual():
 with urllib.request.urlopen('https://raw.githubusercontent.com/aokid666/zz-tuijie-manual-2027/main/data/tuijie-manual-lower.json',timeout=120) as r:d=json.load(r)
 assert all(p.get('ext') for p in d['pages']),'Handbook source OCR is not ready';return d

def find_answer(lines,mpages,scope):
 query=norm(''.join(l['t'] for l in lines));scored=[]
 for pg in mpages:
  if scope and pg['page'] not in scope:continue
  rs=[l for l in pg['lines'] if 20<l['b'][1]<pg['height']-25];raw='\n'.join(l['t'] for l in rs);t=norm(raw);blocks=difflib.SequenceMatcher(None,query,t,autojunk=False).get_matching_blocks();run=max((b.size for b in blocks),default=0);overlap=sum(b.size for b in blocks if b.size>=3);score=overlap/max(1,len(query))
  if run>=6 and overlap>=12:scored.append((score,run,pg,rs))
 if not scored:return [],'',[]
 scored.sort(key=lambda a:(a[0],a[1]),reverse=True);best=scored[0];selected=[best]+[x for x in scored[1:] if x[0]>=.28 and x[1]>=8 and abs(x[2]['page']-best[2]['page'])<=1][:1];refs=[];texts=[];evidence=[]
 for score,run,pg,rs in sorted(selected,key=lambda x:x[2]['page']):
  hits=[]
  for i,l in enumerate(rs):
   t=norm(l['t']);common=max((m.size for m in difflib.SequenceMatcher(None,query,t,autojunk=False).get_matching_blocks()),default=0)
   if common>=5:hits.append(i)
  if hits:
   lo=max(0,min(hits)-1);hi=min(len(rs),max(hits)+3);chosen=rs[lo:hi]
  else:chosen=rs
  y=max(0,chosen[0]['b'][1]-5);bottom=min(pg['height']-20,chosen[-1]['b'][3]+5);refs.append({'page':63+pg['page'],'b':[20,y,pg['width']-40,bottom-y]});texts.append('\n'.join(l['t'] for l in chosen));evidence.append({'source':'tuijie-manual-lower','page':pg['page'],'quote':texts[-1],'method':'official-day-page-range-and-question-text'})
 return refs,'\n\n'.join(texts),evidence

def merged_lines(pg):
 groups=[]
 for line in sorted(pg['lines'],key=lambda l:((l['b'][1]+l['b'][3])/2,l['b'][0])):
  center=(line['b'][1]+line['b'][3])/2
  if groups and abs(center-groups[-1][0])<=3 and all(line['b'][0]>=r['b'][2]-1 or line['b'][2]<=r['b'][0]+1 for r in groups[-1][1]):groups[-1][1].append(line)
  else:groups.append((center,[line]))
 result=[]
 for _,ls in groups:
  ls.sort(key=lambda l:l['b'][0]);text=''
  for i,l in enumerate(ls):text+=(' ______ ' if i and l['b'][0]-ls[i-1]['b'][2]>12 else ' ' if i else '')+l['t']
  result.append({'t':text,'b':[min(l['b'][0] for l in ls),min(l['b'][1] for l in ls),max(l['b'][2] for l in ls),max(l['b'][3] for l in ls)]})
 return result

def reviewed_answer(day,no,manual):
 known={(1,1):(7,'中国共产党一经成立',1,3),(4,2):(14,'第一次提出了“建设有中国特色',0,4),(6,6):(18,'孙中山',0,4),(7,1):(19,'毛泽东思想发展历程',0,18),(7,2):(19,'毛泽东思想发展历程',0,18)}
 key=known.get((day,no))
 if not key:return None
 pn,anchor,before,after=key;pg=manual[pn-1];rs=pg['lines'];i=next(i for i,l in enumerate(rs) if anchor in l['t']);chosen=rs[max(0,i-before):i+after];y=chosen[0]['b'][1]-5;bottom=chosen[-1]['b'][3]+5;quote='\n'.join(l['t'] for l in chosen)
 return [{'page':63+pn,'b':[20,y,pg['width']-40,bottom-y]}],quote,[{'source':'tuijie-manual-lower','page':pn,'quote':quote,'method':'reviewed-source-passage'}]

def main():
 d=json.loads((ROOT/'data'/f'{ID}.json').read_text());ps=d['pages'];manual=read_manual();mp=manual['pages'];assert len(ps)==63
 qs=[];errors=[];days=[]
 for day in range(1,31):
  pages=ps[2*day+1:2*day+3];first=pages[0];pre=''.join(l['t'] for l in first['lines']);m=re.search(r'页码[：:]?P?\s*(\d+)\s*[-—~～一]\s*P?\s*(\d+)',pre,re.I)
  if not m:m=re.search(r'页码[：:]?P?\s*(\d+)',pre,re.I)
  scope=list(range(int(m[1])+6,(int(m[2]) if len(m.groups())>1 else int(m[1]))+7)) if m else []
  if day==29:scope=sorted(set(scope+[88]))
  groups=[];cur=None;started=False;stopped=False;expected=1
  for pg in pages:
   for line in merged_lines(pg):
    text=line['t'].strip()
    if '今日背诵小测试' in text:started=True;continue
    if not started:continue
    if re.search('今日背诵心得|更多测试|扫码做|背练结合自测本|腿姐背诵自测Day',text):
     if '今日背诵心得' in text:
      if cur:cur['end']=(pg['page'],line['b'][1]-3)
      stopped=True
     continue
    if stopped or line['b'][1]<20 or line['b'][3]>pg['height']-20 or (line['b'][1]>pg['height']*.9 and re.fullmatch(r'[·.\s]*\d+[·.\s]*',text)):continue
    h=re.match(r'^(\d{1,2})\s*[.．、。，,:：]\s*(.*)',text) if line['b'][0]<pg['width']*.3 else None
    if h and int(h[1])>expected:errors.append(f'Day {day}: missing question boundary before {h[1]}')
    if h and int(h[1])==expected:
     if cur:cur['end']=(pg['page'],line['b'][1]-3);groups.append(cur)
     cur={'no':expected,'rows':[{**line,'p':pg['page'],'rest':h[2]}],'start':(pg['page'],line['b'][1]-4)};expected+=1
    elif cur:cur['rows'].append({**line,'p':pg['page']})
    elif expected==1:cur={'no':1,'rows':[{**line,'p':pg['page'],'rest':text}],'start':(pg['page'],line['b'][1]-4)};expected=2
  if cur:
   cur.setdefault('end',(cur['rows'][-1]['p'],cur['rows'][-1]['b'][3]+12));groups.append(cur)
  if not groups:errors.append(f'Day {day}: no numbered original test questions')
  for g in groups:
   rows=g['rows'];keyrefs,answer,evidence=reviewed_answer(day,g['no'],mp) or find_answer(rows,mp,scope);qrefs=[]
   for pn in range(g['start'][0],g['end'][0]+1):
    pg=ps[pn-1];y=g['start'][1] if pn==g['start'][0] else 25;bottom=g['end'][1] if pn==g['end'][0] else pg['height']-25
    if bottom>y:qrefs.append({'page':pn,'b':[20,max(0,y),pg['width']-40,min(pg['height'],bottom)-max(0,y)]})
   raw='\n'.join([rows[0]['rest']]+[l['t'] for l in rows[1:]]);chapter=f'Day {day}';no=g['no'];module='腿姐背练结合自测'
   subject='中国近现代史纲要' if day<=11 or 23<=day<=26 else '马克思主义基本原理' if day<=17 else '习近平新时代中国特色社会主义思想概论' if day<=22 else '思想道德与法治'
   qs.append({'id':f'pr-{ID}-written-{day:02}-{no:02}','bookId':ID,'type':'written','source':'p','moduleIdx':13,'module':module,'subject':subject,'chapter':chapter,'chapterTitle':chapter,'section':'原页填空 · 自评核对','no':no,'originalNo':no,'day':day,'stem':'按原图填写空白（可在原题上手写，或在下方输入答案）。\n'+raw,'options':{},'multi':False,'answer':'','qRefs':qrefs,'keyRefs':keyrefs,'analysis':[{'k':'腿姐背诵手册对应原文（用于填空核对）','t':answer or '暂未找到可确认的对应原文，请浏览《腿姐背诵手册》核对，勿将未核实文字当作标准答案。'}],'kPages':[],'sPages':[],'mRefs':[],'aPages':[],'aCrops':[],'extraLectures':evidence,'officialManualPages':scope,'sourceWarning':'原书为填空自测，采用本人核对原文后自评；不自动判定文字答案。','extractionNote':'请在原始题面中查看准确的空白与排版；文字用于搜索。'})
  days.append({'day':day,'questions':len(groups),'manualPhysicalPages':scope})
 report={'questions':len(qs),'days':days,'errors':errors,'answerLocated':sum(bool(q['keyRefs']) for q in qs),'manualSha256':manual['source']['sha256']};dump('parse-report.json',report);dump('draft-questions.json',qs)
 if errors:raise RuntimeError(str(errors))
 pages=ps+mp;urls=[BASE+f'img/{ID}/{p["page"]:03}.{p["ext"]}' for p in ps]+[MBASE+f'img/tuijie-manual-lower/{p["page"]:03}.{p["ext"]}' for p in mp];parts=[{'firstPage':1,'lastPage':len(ps),'url':BASE+'pdf/'+ID+'.pdf'},{'firstPage':len(ps)+1,'lastPage':len(pages),'url':MBASE+'pdf/tuijie-manual-lower.pdf'}]
 book={'id':ID,'title':'腿姐政治背练结合自测本','kind':'exercise','count':len(qs),'counts':{'written':len(qs)},'pages':len(pages),'pageSizes':[{'width':p['width'],'height':p['height']} for p in pages],'pageUrls':urls,'pdfParts':parts,'sourceBase':BASE,'url':parts[0]['url'],'sha256':d['source']['sha256'],'chapters':[{'key':'腿姐背练结合自测 · Day '+str(day),'title':'Day '+str(day),'count':sum(q['day']==day for q in qs),'firstPage':day*2+2} for day in range(1,31)]}
 dump('book.json',book);dump(ID+'.json',{'bookId':ID,'questions':qs,'pages':[{'page':i+1,'width':p['width'],'height':p['height'],'text':p['text']} for i,p in enumerate(pages)]});print(report,flush=True)
if __name__=='__main__':main()
