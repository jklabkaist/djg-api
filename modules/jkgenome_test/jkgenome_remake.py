# mygenome

import sys, os, copy, re, gzip, collections
import pandas as pd
import numpy as np
import jkbasic, jkbio

refFlat_path = './refFlat.txt'
homedir = '~/'

def loadFasta(fastaPath, blacklist=['NR_106988']):

    h = collections.defaultdict(list)
    
    if fastaPath.endswith('.gz'):
        f = gzip.open(fastaPath)
    else:
        f = open(fastaPath)

    seqID = None
    seqL = []

    while 1:
        if fastaPath.endswith('.gz'):
            line = f.readline().decode('UTF-8')
        else:
            line = f.readline()

        if not line or line.startswith('>'):

            if seqID and seqID not in blacklist:
                h[seqID].append(''.join(seqL))
                seqL = []

            if line:
                seqID = line.split('|')[0].split(' ')[0][1:]
            else:
                break

        else:

            seqL.append(line.rstrip())

    return h

def loadAppris_refseq(path):

    h = collections.defaultdict(list)

    for line in open(path):

        tokL = line[:-1].split('\t')

        if tokL[2][:3] == 'NM_' and tokL[4].startswith('PRINCIPAL'):
            h[tokL[0]].append((tokL[2],tokL[4]))

    for h_key in h.keys():
        h[h_key].sort
    
    return h

def processBlatLine(line):

    tokL = line.rstrip().split('\t')

    h = {}

    h['transName'] = tokL[0]
    h['transID'] = tokL[1]
    h['chrom'] = tokL[2]
    h['chrNum'] = tokL[2][3:]
    h['strand'] = tokL[3]
    h['txnSta'] = int(tokL[4])
    h['txnEnd'] = int(tokL[5])
    h['txnLen'] = int(tokL[5]) - int(tokL[4])
    h['cdsSta'] = int(tokL[6])
    h['cdsEnd'] = int(tokL[7])
    h['exnList'] = list(map(lambda x,y: (int(x),int(y)), tokL[9].split(',')[:-1], tokL[10].split(',')[:-1]))

    if len(tokL) > 12:
        h['geneName'] = tokL[12]
    
    frontL, backL, exnLenList, cdsList, intron = [],[],[],[],[]

    f_len, b_len, c_len = 0, 0, 0
    if h['cdsSta'] != h['cdsEnd']:
        
        i = 0
        
        def cal_Fuct(F_s, F_e, F_list, F_len):
            F_diff = F_e - F_s
            if F_diff > 0:
                F_list.append((F_s, F_e))
                F_len += F_diff
            return F_list, F_len
        
        for (s,e) in h['exnList']:
            exnLenList.append(e - s)
            cds_s, cds_e = h['cdsSta'], h['cdsEnd']
            
            frontL, f_len = cal_Fuct(min(s, cds_s), min(e, cds_s), frontL, f_len)
            backL, b_len = cal_Fuct(max(s, cds_e), max(e, cds_e), backL, b_len)
            cdsList, c_len = cal_Fuct(max(s, cds_s), min(e, cds_e), cdsList, c_len)
            
            if i != 0:
                intron.append((pre_e, s))
            pre_e = e
            i += 1
    
    h['exnLenList'] = exnLenList
    h['cdsList'] = cdsList
    h['intron'] = intron
    h['exnLen'] = sum(h['exnLenList'])
    h['cdsLen'] = c_len
    
    if h['strand'] == '+':
            h['utr5'] = frontL
            h['utr5Len'] = f_len
            h['utr3'] = backL
            h['utr3Len'] = b_len
    else:
            h['utr5'] = backL
            h['utr5Len'] = b_len
            h['utr3'] = frontL
            h['utr3Len'] = f_len
    
    return h

def refFlat_as_DF(blatOutputPath):
        
    col_name = ['transName','transID','chrom','strand','txnSta','txnEnd','cdsSta','cdsEnd','exnNum','exnSta','exnEnd']
    refFlat = pd.read_csv('./refFlat.txt', sep='\t', names=col_name, header=None)
    refFlat.insert(6, 'txnLen', refFlat['txnEnd'] - refFlat['txnSta'])
    refFlat['exnSta'] = refFlat['exnSta'].apply(np.fromstring,sep=',',dtype=int)
    refFlat['exnEnd'] = refFlat['exnEnd'].apply(np.fromstring,sep=',',dtype=int)

    return refFlat

def refFlat_cal(refFlat):
    refFlat = refFlat.reset_index(drop=True)
    
    def sep_exn(F_strand, F_exnSta, F_exnEnd, F_cdsSta, F_cdsEnd):
        F_intron = np.transpose([F_exnEnd[:-1], F_exnSta[1:]])
        F_exnLst = np.transpose([F_exnSta,F_exnEnd])
        F_exnLen = np.diff(F_exnLst)
        F_exnSum = sum(F_exnLen)
        
        if F_cdsSta != F_cdsEnd and len(F_exnSta) > 1:
            
            front_index = np.searchsorted(F_exnEnd,F_cdsSta)+1
            back__index = np.searchsorted(F_exnSta,F_cdsEnd)+1
            F_exnList = np.sort(np.concatenate((F_exnLst, [[F_cdsSta,F_cdsSta],[F_cdsEnd,F_cdsEnd]])),axis=0)
            F_middl_lst = F_exnList[front_index:back__index]
           
            if F_strand == '+':
                F_front_lst = F_exnList[:front_index]
                F_back__lst = F_exnList[back__index:]
            
            else:
                F_back__lst = F_exnList[:front_index]
                F_front_lst = F_exnList[back__index:]
            
            def LLS_cal(FF_lst):
                FF_len = np.diff(FF_lst)
                FF_TF = FF_len.astype(bool).flatten()
                FF_lst = FF_lst[FF_TF]
                FF_len = FF_len[FF_TF]
                FF_sum = sum(FF_len)
                return FF_len, FF_lst, FF_sum
            
            F_front_len, F_front_lst, F_front_sum = LLS_cal(F_front_lst)
            F_middl_len, F_middl_lst, F_middl_sum = LLS_cal(F_middl_lst)
            F_back__len, F_back__lst, F_back__sum = LLS_cal(F_back__lst)

        else:
            F_front_lst, F_back__lst = [],[]
            F_middl_lst = F_exnLst
            F_middl_len = np.diff(F_middl_lst)
            F_middl_sum = sum(F_middl_len)
            F_front_len, F_back__len = [],[]
            F_front_sum, F_back__sum = 0, 0
        
        return [F_exnLst, F_exnLen, F_exnSum, F_front_lst, F_front_len, F_front_sum, F_middl_lst, F_middl_len, F_middl_sum, F_back__lst, F_back__len, F_back__sum, F_intron]
    
    sep_UTR = pd.DataFrame(map(lambda x1,x2,x3,x4,x5:sep_exn(x1,x2,x3,x4,x5),\
                               refFlat['strand'], refFlat['exnSta'], refFlat['exnEnd'], refFlat['cdsSta'], refFlat['cdsEnd']),\
                               columns=['exnList', 'exnLenList', 'exnLen', 'utr5','utr5LenList','utr5Len','cdsList','cdsLenList','cdsLen','utr3','utr3LenList','utr3Len','intron'])
    refFlat = refFlat.merge(sep_UTR,right_index=True,left_index=True)
    
    return refFlat

def loadBlatOutput(blatOutputPath,by='transID',blacklist=['NR_106988']):

    h = collections.defaultdict(list)

    if blatOutputPath.endswith('.gz'):
        f = gzip.open(blatOutputPath)
    else:
        f = open(blatOutputPath)

    for line in f:

        if line[0] == '#':
            continue
        
        if blatOutputPath.endswith('.gz'):
            line = line.decode('UTF-8')
        
        r = processBlatLine(line)

        if r['transID'] in blacklist:
            continue

        h[r[by]].append(r)

    from operator import itemgetter

    for k,vL in list(h.items()):
        h[k] = sorted(vL,key=itemgetter('txnSta','txnEnd'))

    return h

def loadBlatOutputByGene(blatOutputPath):

    return loadBlatOutput(blatOutputPath, 'geneName')

def loadBlatOutputByChr(blatOutputPath):

    return loadBlatOutput(blatOutputPath, 'chrom')

def loadBlatOutputByID(blatOutputPath):

    return loadBlatOutput(blatOutputPath,'transID')

def loadRefFlatByChr(blatOutputPath):

    return loadBlatOutput(blatOutputPath,'chrom')

def loadRefFlatByGeneName(blatOutputPath):

    return loadBlatOutput(blatOutputPath,'transName')

class locus: # UCSC type
    
    def __init__(self,loc,id=''):
        loc = loc.replace('..','-')
        rm = re.match('([^:]+):([0-9,]+)-([0-9,]+)([+-])',loc) # base-0, base-1
        self.chrom = rm.group(1)
        self.chrSta = int(rm.group(2))
        self.chrEnd = int(rm.group(3))
        self.strand = rm.group(4)
        if self.chrom[:3] == 'chr':
            self.chrNum = rm.group(1)[3:]
        else:
            self.chrNum = None
        self.id = id
    
    def toString(self,style='UCSC'):
    
        if style=='gsnap':
            return '%s%s:%s..%s' % (self.strand,self.chrom,self.chrSta+1,self.chrEnd)
        else:
            return '%s:%s-%s%s' % (self.chrom,self.chrSta,self.chrEnd,self.strand)
    
    def overlap(self,region):
    
        return overlap((self.chrom,self.chrSta,self.chrEnd),region)

    def overlappingGeneL(self,refFlatH=None,refFlatFileName='~/D/Sequences/ucsc_hg19_ref/refseq',strand_sensitive=False):
    
        gL = set()
    
        if refFlatH == None and refFlatFileName != '':
            refFlatH = loadRefFlatByChr(refFlatFileName)
        
        if self.chrom not in refFlatH:
            return []
    
        for l in refFlatH[self.chrom]:
        
            if strand_sensitive:
            
                if self.overlap((l['chrom'],l['txnSta'],l['txnEnd'])) > 0 and self.strand==l['strand']:
                    gL.add(l['geneName'])
                
            else:
            
                if self.overlap((l['chrom'],l['txnSta'],l['txnEnd'])) > 0:
                    gL.add(l['geneName'])
                
        return tuple(gL)
    
    def regionType(self,h = 0):
        if h == 0:
            h = loadBlatOutputByChr(refFlat_path)
        return getRegionType(h,self)
    
    
    def twoBitFrag(self, assembly, buffer5p=0, buffer3p=0):
    
        twoBitFilePath='/%s/D/Sequences/%s/%s.2bit' % (homedir,assembly,assembly)
    
        if self.strand == '+':
            staPos = self.chrSta - buffer5p
            endPos = self.chrEnd + buffer3p
        else:
            staPos = self.chrSta - buffer3p
            endPos = self.chrEnd + buffer5p
        
        fragFile = os.popen('%s/tools/jkent/twoBitToFa %s:%s:%s-%s stdout' % (homedir, twoBitFilePath, self.chrom, staPos, endPos), 'r')
        fragFile.readline()
    
        seq = fragFile.read().replace('\n','').rstrip().upper()
    
        if self.strand == '+':
            return seq
        else:
            return jkbio.rc(seq)

# don't understand
def getRegionType(h,loc): # locusTupe = (chrom,sta,end) 1-base

    locT = (loc.chrom,loc.chrSta+1,loc.chrEnd)

    regions = []

    for t in h[locT[0]]:

        if t['txnEnd'] < locT[1]:
            continue

        elif locT[2] <= t['txnSta']:
            break

        if t['strand']==loc.strand:
            sense = 'sense'
        else:
            sense = 'antisense'

        flag = None

        for regionName in ['cdsList','utr5','utr3','intron']:

            for s,e in t[regionName]:

                if overlap(('_',locT[1]-1,locT[2]),('_',s,e)) == 0:
                   continue

                if regionName == 'cdsList':

                    if locT[2]-locT[1] == 0:

                        offset = 0

                        for s,e in t['cdsList']:
                            offset += min(e,locT[1])-min(s,locT[1])

                        frame = (offset-1) % 3

                        if t['strand'] == '-':
                            frame= 2-frame

                        flag = 'cds_%d_%d' % (offset-1,frame)

                    else:

                        flag = 'cds_m'

                else:

                    flag = regionName

                marg = margin((locT[1]-1,locT[2]),(s,e))
                regions.append((t['transName'],t['transID'],flag, sense, marg))

        if t['cdsList'] == []:
            regions.append((t['transName'],t['transID'],'lnc', sense, -1))

    return list(set(regions))


def margin(innerRange,outerRange): # 0-base

    i_s,i_e = innerRange
    o_s,o_e = outerRange

    return i_s-o_s, o_e-i_e


def overlap(x,y): # s: base-0, e: base-1

    c1,s1,e1 = x
    c2,s2,e2 = y

    if c1 != c2 or e2<=s1 or e1<=s2:
        return 0

    s = max(s1,s2)
    e = min(e1,e2)

    if s < e:
        return e-s
    else:
        return 0

# need twoBitToFa
def mergeLoci(locusL,gap=10):

    if len(set([x.strand for x in locusL]))>1 or len(set([x.chrNum for x in locusL]))>1:
        print ('warning: heterogeneous mix of loci')
        print (locusL)
        return locusL

    locusL.sort(key=lambda x: x.chrEnd)
    locusL.sort(key=lambda x: x.chrSta)

    locusMergedL = []

    i = 0

    while i < len(locusL):

        chrS1, chrE1 = locusL[i].chrSta, locusL[i].chrEnd

        curE = chrE1

        j = i+1

        idL = [locusL[i].id]

        while j < len(locusL):

            chrS2, chrE2 = locusL[j].chrSta, locusL[j].chrEnd

            if curE + gap < chrS2:
                break

            curE = max(curE,chrE2)
            idL.append(locusL[j].id)

            j += 1

        newLocus = copy.deepcopy(locusL[i])
        newLocus.chrEnd = max(locusL[k].chrEnd for k in range(i,j))
        newLocus.id = '|'.join(idL)

        locusMergedL.append(newLocus)

        i = j

    return locusMergedL

# no software
def mes5(seq): # seq example: CAGgtaagt

    if len(seq) != 9:
        raise Exception

    return float(os.popen('cd %s/tools/maxentscan; perl score5_mod.pl %s' % (homedir,seq)).readline())

def mes3(seq): # seq example: ttccaaacgaacttttgtagGGA

    if len(seq) != 23:
        raise Exception

    return float(os.popen('cd %s/tools/maxentscan; perl score3_mod.pl %s' % (homedir,seq)).readline())

def mes5_scan(seq):

    seq = seq.upper()

    resultL = [None]*3

    for i in range(len(seq)-8):
        if seq[i+3:i+5] == 'GT':
            resultL.append(mes5(seq[i:i+9]))
        else:
            resultL.append(None)

    resultL += [None]*5

    resultL = [(0 if x==None or x<0 else x) for x in resultL]

    return resultL

def mes3_scan(seq):

    seq = seq.upper()

    resultL = [None]*19

    for i in range(len(seq)-22):
        if seq[i+18:i+20] == 'AG':
            resultL.append(mes3(seq[i:i+23]))
        else:
            resultL.append(None)

    resultL += [None]*3

    resultL = [(0 if x==None or x<0 else x) for x in resultL]

    return np.array(resultL)

def mes_byCoord(chrNum,pos,strand,ref,alt,assembly,verbose=False): # assuming single nt to single nt change, base-1 inclusive

    l = locus('chr%s:%s-%s%s' % (chrNum,pos-23,pos+22,strand))

    s_before = l.twoBitFrag(assembly)

    if s_before[22:22+len(ref)] != ref:
        print((s_before, ref, alt))
        raise Exception

    s_after = s_before[:22] + alt + s_before[-22:]

    mes5_tup = (mes5_scan(s_before[14:-14]),mes5_scan(s_after[14:-14]),)
    mes3_tup = (mes3_scan(s_before),mes3_scan(s_after),)

    mes5_dt = np.array(mes5_tup[1])-np.array(mes5_tup[0])
    mes3_dt = np.array(mes3_tup[1])-np.array(mes3_tup[0])

    if verbose:
        return mes5_dt,mes3_dt,mes5_tup[1],mes3_tup[1]
    else:
        return mes5_dt,mes3_dt

def mes_byCoord_subs(chrNum,chrSta,chrEnd,strand,ref,alt,assembly,verbose=False): # assuming substitution, base-1 inclusive

    l = locus('chr%s:%s-%s%s' % (chrNum,chrSta-23,chrEnd+22,strand))

    s_before = l.twoBitFrag(assembly)

    if s_before[22:22+len(ref)] != ref:
        print((s_before, ref, alt))
        raise Exception

    s_after = s_before[:22] + alt + s_before[-22:]

    mes5_tup = (mes5_scan(s_before[14:-14]),mes5_scan(s_after[14:-14]),)
    mes3_tup = (mes3_scan(s_before),mes3_scan(s_after),)

    mes5_dt = np.array(mes5_tup[1])-np.array(mes5_tup[0])
    mes3_dt = np.array(mes3_tup[1])-np.array(mes3_tup[0])

    if verbose:
        return mes5_dt,mes3_dt,mes5_tup,mes3_tup
    else:
        return mes5_dt,mes3_dt

def mes_byCoord_general(chrNum,chrSta,chrEnd,strand,ref,alt,assembly): # base-0 exclusive

    ref = '' if ref=='-' else ref
    alt = '' if alt=='-' else alt

    l = locus('chr%s:%s-%s%s' % (chrNum,chrSta-22,chrEnd+22,strand))

    s_before = l.twoBitFrag(assembly)

    if s_before[22:22+len(ref)] != ref:
        print((s_before, chrNum, chrSta, chrEnd, ref, alt))
        raise Exception

    s_after = s_before[:22] + alt + s_before[-22:]

    mes5_tup = (mes5_scan(s_before[14:-14]),mes5_scan(s_after[14:-14]),)
    mes3_tup = (mes3_scan(s_before),mes3_scan(s_after))

    return mes5_tup,mes3_tup

def mes5_byCoord(chrNum,pos,strand,assembly): # pos is 1-base sta or end of intron

    if strand == '+':
        l = locus('chr%s:%s-%s%s' % (chrNum,pos-4,pos+5,'+'))
    else:
        l = locus('chr%s:%s-%s%s' % (chrNum,pos-6,pos+3,'-'))

    s = l.twoBitFrag(assembly)
    return s,mes5(s)

def mes3_byCoord(chrNum,pos,strand,assembly): # pos is 1-base sta or end of intron

    if strand == '+':
        l = locus('chr%s:%s-%s%s' % (chrNum,pos-20,pos+3,'+'))
    else:
        l = locus('chr%s:%s-%s%s' % (chrNum,pos-4,pos+19,'-'))

    s = l.twoBitFrag(assembly)
    return s,mes3(s)

# not used
def tbi_bed_query(bedFilePath,locusStr):

    f = os.popen('~/tools/tabix-0.2.6/tabix %s %s' % (bedFilePath,locusStr),'r')

    return f.readlines()

# no software
def spliceAI_run(chrom,pos,ref,alt): # hg38, pos-1; indel exam: T to TA

    vcf = '''##fileformat=VCFv4.2
##fileDate=20191004
##reference=GRCh38/hg38
##contig=<ID=chr1,length=248956422>
##contig=<ID=chr2,length=242193529>
##contig=<ID=chr3,length=198295559>
##contig=<ID=chr4,length=190214555>
##contig=<ID=chr5,length=181538259>
##contig=<ID=chr6,length=170805979>
##contig=<ID=chr7,length=159345973>
##contig=<ID=chrX,length=156040895>
##contig=<ID=chr8,length=145138636>
##contig=<ID=chr9,length=138394717>
##contig=<ID=chr11,length=135086622>
##contig=<ID=chr10,length=133797422>
##contig=<ID=chr12,length=133275309>
##contig=<ID=chr13,length=114364328>
##contig=<ID=chr14,length=107043718>
##contig=<ID=chr15,length=101991189>
##contig=<ID=chr16,length=90338345>
##contig=<ID=chr17,length=83257441>
##contig=<ID=chr18,length=80373285>
##contig=<ID=chr20,length=64444167>
##contig=<ID=chr19,length=58617616>
##contig=<ID=chrY,length=57227415>
##contig=<ID=chr22,length=50818468>
##contig=<ID=chr21,length=46709983>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
%s\t%s\t.\t%s\t%s\t.\t.\t.\n''' % (chrom,pos,ref,alt)

    import tempfile

    f = tempfile.NamedTemporaryFile()
    f.write(vcf); f.flush()

    return os.popen("cat %s | spliceai -R %s/D/Sequences/hg38/hg38.fa -A grch38" % (f.name,homedir)).readlines()

def spliceAI_raw(locusStr): # locusStr: 1-base, 1-base

    if locusStr[:3] == 'chr':
        locusStr = locusStr[3:]

    return tbi_bed_query('%s/BigFiles/SpliceAI/spliceai_scores.raw.snv.hg38.vcf.gz' % homedir, locusStr) + tbi_bed_query('%s/BigFiles/SpliceAI/spliceai_scores.raw.indel.hg38.vcf.gz' % homedir, locusStr)

def primateAI_raw(locusStr): # locusStr: 1-base, 1-base

    if locusStr[:3] != 'chr':
        locusStr = 'chr'+locusStr

    chrom = locusStr.split(':')[0]
    posSta,posEnd = list(map(int,locusStr.split(':')[-1].split('-')))

    locusStr_new = '%s:%s-%s' % (chrom,posSta-1,posSta+1)

    return tbi_bed_query('%s/BigFiles/primateAI/primateAI_hg38.bed.gz' % homedir, locusStr_new)

def spliceAI(locusStr): # locusStr: 1-base, 1-base

    result = []

    for r in spliceAI_raw(locusStr):
        
        tokL = r[:-1].split('\t')

        chrN = tokL[0]
        pos = int(tokL[1])

        ref = tokL[3] 
        alt = tokL[4]

        tL = tokL[-1].split('|')

        geneName = tL[1]

        score = dict(list(zip(('AG','AL','DG','DL'),list(map(float,tL[2:6])))))
        relPos = dict(list(zip(('AG','AL','DG','DL'),list(map(int,tL[6:])))))

        result.append({'chrN':chrN,'pos':pos,'ref':ref,'alt':alt,'geneName':geneName,'score':score,'relPos':relPos})

    return result

def calColor(score):

    ceiling = 2

    if score>0:
        return (1,1-min(score,ceiling)/ceiling,1-min(score,ceiling)/ceiling)
    elif score<0:
        return (1-max(score,-ceiling)/-ceiling,1-max(score,-ceiling)/-ceiling,1)
    else:
        return (1,1,1)

# missing file
def variant_bi(chrNum,chrPos,strand,ref,alt,assembly='hg38',hexH4=False): # ref, alt: transcript base

    if not hexH4:
        hexH4 = load_hexamer4() 

    print('Hexamer')
    print(hexamer4_byCoord_general(chrNum,chrPos,chrPos,strand,ref,alt,hexH4,assembly))
    print()

    mes_result = mes_byCoord(chrNum,chrPos,strand,ref,alt,assembly,verbose=True) 

    print('MES donor')
    print('delta', list(map(float,list(mes_result[0]))))
    print('final', list(map(float,mes_result[2])))

    print('MES acceptor')
    print('delta', list(map(float,list(mes_result[1]))))
    print('final', list(map(float,mes_result[3])))

def labranchor_query(locusStr):

    return tbi_bed_query('~/D/DB/labranchor/lstm.gencode_v19.hg38.top.sorted.bed.gz', locusStr)

def load_hexamer(segType):

    if segType == '5p_exon':
        s = ('A5','R1')
    elif segType == '5p_intron':
        s = ('A5','R2')
    elif segType == '3p_intron':
        s = ('A3','R1')
    elif segType == '3p_exon':
        s = ('A3','R2')
    else:
        print(('segType unknown: %s\n' % segType))
        raise Exception

    import dnatools

    return pd.Series(index=dnatools.make_mer_list(6),data=np.load('%s/Packages/cell-2015/results/N4_Motif_Effect_Sizes/%sSS/mean_effects_sdpos_%s.npy' % (homedir,s[0],s[1])))

def load_hexamer4():

    result = {}

    for h in ['5p_exon','3p_exon','5p_intron','3p_intron']:
        result[h] = load_hexamer(h)
    
    return result

def hexamer(seq,hexH): 

    resultL = []

    for i in range(len(seq)-5):
        
        s = seq[i:i+6]
        resultL.append(hexH[s])

    return pd.Series(resultL)

def hexamer_byCoord(chrNum,pos,strand,ref,alt,hexH,assembly,verbose=False):

    l = locus('chr%s:%s-%s%s' % (chrNum,pos-6,pos+5,strand))

    s_before = l.twoBitFrag(assembly)

    if s_before[5:5+len(ref)] != ref:
        print((s_before, ref, alt))
        raise Exception

    s_after = s_before[:5] + alt + s_before[-5:]

    scores_after = hexamer(s_after,hexH)
    scores_before = hexamer(s_before,hexH)

    if verbose:
        print((scores_before, scores_after, scores_after - scores_before))

    return sum(scores_after - scores_before)

def hexamer4_byCoord_general(chrNum,chrSta,chrEnd,strand,ref,alt,hexH4,assembly): # pos, 0-base, inclusive

    ref = '' if ref=='-' else ref
    alt = '' if alt=='-' else alt

    l = locus('chr%s:%s-%s%s' % (chrNum,chrSta-5,chrEnd+5,strand))

    s_before = l.twoBitFrag(assembly)

    if s_before[5:5+len(ref)] != ref:
        print((s_before, ref, alt))
        raise Exception

    s_after = s_before[:5] + alt + s_before[-5:]

    if 'N' in s_before or 'N' in s_after:
        print(s_before,s_after)
        raise Exception

    result = {}

    for h,hexH in list(hexH4.items()):

        scores_after = hexamer(s_after,hexH)
        scores_before = hexamer(s_before,hexH)

        result[h] = sum(scores_after) - sum(scores_before)

    return result

# missing file
def geneNameH(refFlatFileName='/Z/Sequence/ucsc_hg19/annot/refFlat.txt', knownToRefSeqFileName='/Z/Sequence/ucsc_hg19/annot/knownToRefSeq.txt', \
        hugoFileName='/Z/Sequence/geneinfo/hugo.txt'):

    geneNameH = {}

    for line in open(refFlatFileName):

        h = processBlatLine(line)

        geneNameH[h['refSeqId']] = h['geneName']
        geneNameH[h['geneName']] = h['geneName']

    for line in open(knownToRefSeqFileName):

        (knownId,refSeqId) = line[:-1].split('\t')

        try:
            geneNameH[knownId] = geneNameH[refSeqId]
        except:
            pass

    for line in open(hugoFileName):

        (geneName,geneDesc,aliases,geneCardNames,refSeqIds) = line[:-1].split('\t')

        for refSeqId in refSeqIds.split(','):
            
            if refSeqId not in geneNameH:
                geneNameH[refSeqId] = geneName

        for alias in aliases.split(','):

            if alias not in geneNameH:
                geneNameH[alias] = geneName

        for geneCardName in geneCardNames.split(','):

            geneNameH[geneCardName] = geneName

    return geneNameH

# missing file
def geneSetH(biocartaFileName='/Z/Sequence/geneinfo/BIOCARTA.gmt', goFileName='/Z/Sequence/geneinfo/GO.gmt', keggFileName='/Z/Sequence/geneinfo/KEGG.gmt'):

    geneSetH = {'biocarta':{}, 'go':{}, 'kegg':{}}

    for line in open(biocartaFileName):

        tokL = line[:-1].split('\t')
        geneSetH['biocarta'][tokL[0]] = (tokL[1],tuple(tokL[2:]))

    for line in open(goFileName):

        tokL = line[:-1].split('\t')
        geneSetH['go'][tokL[0]] = (tokL[1],tuple(tokL[2:]))

    for line in open(keggFileName):

        tokL = line[:-1].split('\t')
        geneSetH['kegg'][tokL[0]] = (tokL[1],tuple(tokL[2:]))

    return geneSetH

# missing file
def geneInfoH(geneNameH, geneSetH, refSeqSummaryFileName='/Z/Sequence/ucsc_hg19/annot/refSeqSummary.txt', hugoFileName='/Z/Sequence/geneinfo/hugo.txt', \
        censusFileName='/Z/Sequence/geneinfo/cancer_gene_census.txt', biocartaFileName='/Z/Sequence/geneinfo/BIOCARTA.gmt', \
        goFileName='/Z/Sequence/geneinfo/hugo.txt', keggFileName='/Z/Sequence/geneinfo/hugo.txt'):

    geneInfoH = {}

    for line in open(refSeqSummaryFileName):

        (refSeqId,status,summary) = line[:-1].split('\t')

        if refSeqId in geneNameH:

            geneName = geneNameH[refSeqId]

            if geneName not in geneInfoH:
                geneInfoH[geneName] = {}

            geneInfoH[geneName]['summary'] = summary

    for line in open(hugoFileName):

        (geneName,desc,aliases,geneCardName,refSeqIds) = line[:-1].split('\t')

        if geneName not in geneInfoH:
            geneInfoH[geneName] = {}

        geneInfoH[geneName]['desc'] = desc 
        geneInfoH[geneName]['aliases'] = aliases
        geneInfoH[geneName]['refSeqIds'] = refSeqIds

    for line in open(censusFileName):

        tokL = line[:-1].split('\t')

        (geneName,desc,somatic,germline,mutType,translocPartners) = (tokL[0],tokL[1],tokL[7],tokL[8],tokL[12],tokL[13])

        if geneName == 'Symbol':
            continue

        if geneName not in geneInfoH:
            geneInfoH[geneName] = {'desc':desc}

        geneInfoH[geneName]['census_somatic'] = somatic
        geneInfoH[geneName]['census_germline'] = germline
        geneInfoH[geneName]['census_mutType'] = mutType
        geneInfoH[geneName]['census_translocPartners'] = translocPartners


    for geneSetDB in list(geneSetH.keys()):

        for (geneSetName,(geneSetDesc,geneNameL)) in geneSetH[geneSetDB].items():

            for geneName in geneNameL:

                if geneName in geneInfoH:
                    jkbasic.addHash(geneInfoH[geneName],geneSetDB,(geneSetName,geneSetDesc))
                else:
                    geneInfoH[geneName] = {geneSetDB:[(geneSetName,geneSetDesc)]}

    return geneInfoH

# not used
def convertTrans2Genome(blatH,transID,transPos,transLen=-1): # pos base-1

    result = []

    for trans in blatH[transID]:

        if '_' in  trans['chrom']:
            continue

        if transLen == -1:
            transLen = trans['exnLen']

        if trans['strand'] == '-':
            transPos = transLen-transPos+1

        tally = 1

        for i,n in enumerate(trans['exnLenList']):

            if tally <= transPos < tally+n:
                result.append((trans['chrom'], trans['exnList'][i][0]+(transPos-tally)+1, trans['strand'])) # pos base-1
                break

            tally += n

    return result

# not used
def convertGenome2Trans(blatH_byChr,chrNum,gPos): # genomic pos base1, transcript pos base0

    if 'chr'+str(chrNum) not in blatH_byChr:
        return []

    result = []

    for trans in blatH_byChr['chr'+str(chrNum)]:

        if trans['txnEnd'] < gPos:
            continue
        elif gPos <= trans['txnSta']:
            break

        for i,n in enumerate(trans['exnList']):

            if n[1] < gPos:
                continue
            elif gPos <= n[0]:
                break

            annot = getRegionTypeUsingTransH(trans, gPos)

            if trans['strand'] == '+':
                result.append((trans, sum([min(e[1],gPos)-min(e[0],gPos) for e in trans['exnList']])-1, annot))
            else:
                result.append((trans, sum([max(e[1],gPos)-max(e[0],gPos) for e in trans['exnList']]), annot))

            break

    return result

def getRegionTypeUsingTransH(transH,gPos): # transH: individual transcript hash; gPos: 1-base

    if len(transH['cdsList']) == 0:
        return 'lnc'

    if sum([int(e[0]<gPos<=e[1]) for e in transH['utr3']]) > 0:
        return 'utr3'
    elif sum([int(e[0]<gPos<=e[1]) for e in transH['utr5']]) > 0:
        return 'utr5'
    elif sum([int(e[0]<gPos<=e[1]) for e in transH['cdsList']]) > 0:
        return 'cds'
    else:
        print((transH,gPos))
        raise Exception

# not used
def hexamer_track(seq,hexH4=None,figPath='default'):

    if not hexH4:
        hexH4 = load_hexamer4()
 
    from matplotlib.font_manager import FontProperties
    import pylab

    font = FontProperties()
    font.set_family('monospace')
    font.set_size(17.*84./50*7/15)       

    fig = pylab.figure(figsize=(7*len(seq)/50.,7))

    regionType = ['5p_exon','5p_intron','3p_exon','3p_intron']

    scoreH = {}

    for r in range(4):

        ax = fig.add_subplot('41%s' % (r+1,))
        ax.axis([0,len(seq),0,6])
        ax.set_ylabel(regionType[r])
        
        if r==0:
            ax.set_title('Hexamer score')
        
        scoreH[regionType[r]] = {}

        for i in range(len(seq)-5):
            s = seq[i:i+6]
            c = calColor(hexH4[regionType[r]][s])
            scoreH[regionType[r]][s] = hexH4[regionType[r]][s]
            ax.text(i,i%6+0.2,s,color=c,fontproperties=font)
        
    if figPath == 'default':
        fig.savefig('%s/hexamer_track.pdf' % homedir)
    elif figPath:
        fig.savefig(figPath)

    return scoreH

# not used
class transcript:

    def __init__(self,geneName,refFlatFileName='%s/Data/DB/refFlat_hg19.txt' % homedir,assembly='hg19'):  # return the longest transcript matching geneName

        rows = list(map(processBlatLine,os.popen('grep "^%s    " %s' % (geneName,refFlatFileName)).readlines()))
        rows = [x for x in rows if not '_' in x['chrNum']]

        if len(rows)==0:
            raise InitiationFailureException()

        rows.sort(); row = rows[0] # take refSeq with longest coding region

        self.assembly = assembly

        self.geneName = row['geneName']
        self.refSeqId = row['refSeqId']
        self.chrom = row['chrom']
        self.chrNum = row['chrNum']
        self.strand = row['strand']

        self.txnLen = row['txnLen']

        self.exnList = row['exnList']
        self.exnLen = row['exnLen']

        self.cdsList = row['cdsList']
        self.cdsLen = row['cdsLen']

    def txnOverlap(self,region):

        return overlap((self.chrNum,self.exnList[0][0],self.exnList[-1][-1]),region)

    def cdsOverlap(self,region):

        total = 0

        for (cdsS,cdsE) in self.cdsList:

            total += overlap((self.chrNum,cdsS,cdsE),region)

        return total

    def exnOverlap(self,region):

        total = 0

        for (exnS,exnE) in self.exnList:

            total += overlap((self.chrNum,exnS,exnE),region)

        return total

# not used
def loadCensus(censusFileName):

    censusH = {}

    for line in open(censusFileName):

        tokL = line[:-1].split('\t')

        (geneName,desc,somatic,germline,role,mutType,translocPartners) = \
            (tokL[0],tokL[1],tokL[7],tokL[8],tokL[12],tokL[13],tokL[14])

        if geneName == 'Gene Symbol':
            continue

        censusH[geneName] = {'desc':desc}
        censusH[geneName]['somatic'] = somatic
        censusH[geneName]['germline'] = germline
        censusH[geneName]['role'] = role
        censusH[geneName]['mutType'] = mutType
        censusH[geneName]['translocPartners'] = translocPartners
    
    return censusH

# not used
def loadCensus1(censusFileName):

    censusH = {}

    for line in open(censusFileName):

        tokL = line[:-1].split('\t')

        (geneName,desc,somatic,germline,role,mutType,translocPartners) = \
            (tokL[0],tokL[1],tokL[7],tokL[8],tokL[12],tokL[13],tokL[14])

        if geneName == 'Gene Symbol':
            continue

        censusH[geneName] = {'desc':desc}
        censusH[geneName]['somatic'] = somatic
        censusH[geneName]['germline'] = germline
        censusH[geneName]['role'] = role
        censusH[geneName]['mutType'] = mutType
        censusH[geneName]['translocPartners'] = translocPartners
    
    return censusH

# not used
class gene:


    def __init__(self,identifier,geneNameH=None,geneSetH=None,geneInfoH=None,geneDB={}):

        if geneDB != {}:

            if 'geneNameH' in geneDB:
                self.geneNameH = geneDB['geneNameH']
            else:
                self.geneNameH = geneNameH()

            if 'geneSetH' in geneDB:
                self.geneSetH = geneDB['geneSetH']
            else:
                self.geneSetH = geneSetH()

            if 'geneInfoH' in geneDB:
                self.geneInfoH = geneDB['geneInfoH']
            else:
                self.geneInfoH = geneInfoH(self.geneNameH,self.geneSetH)

            try:
                self.geneName = self.geneNameH[identifier]
            except:
                self.geneName = None

            if self.geneName and self.geneName in self.geneInfoH:
                self.geneInfo = self.geneInfoH[self.geneName]
            else:
                self.geneInfo = {}

        else:

            if geneNameH:
                self.geneNameH = geneNameH
            else:
                self.geneNameH = geneNameH()

            if geneSetH:
                self.geneSetH = geneSetH
            else:
                self.geneSetH = geneSetH()

            if geneInfoH:
                self.geneInfoH = geneInfoH
            else:
                self.geneInfoH = geneInfoH(geneNameH,geneSetH)

            try:
                self.geneName = self.geneNameH[identifier]
            except:
                self.geneName = None

            if self.geneName and self.geneName in geneInfoH:
                self.geneInfo = geneInfoH[self.geneName]
            else:
                self.geneInfo = {}

    def getAttr(self,attr):

        if attr in self.geneInfo:
            return self.geneInfo[attr]
        else:
            return ''

# not used, what loadKgByChr?
def getFrameInfoH():

    kgH = loadKgByChr()
    frameInfoH = {}

    for chrom in list(kgH.keys()):
        
        for t in kgH[chrom]:
            frameInfoH[t['geneId']] = t['frame']

    return frameInfoH

# not used
def frameCons(transId1,exnNum1,transId2,exnNum2,frameInfoH):
    
    if transId1 in frameInfoH:
        frame1 = frameInfoH[transId1][exnNum1-1][1]
    else:
        frame1 = None

    if transId2 in frameInfoH:
        frame2 = frameInfoH[transId2][exnNum2-1][0]
    else:
        frame2 = None

    if None not in (frame1,frame2):
        if ((2-frame1) + frame2) % 3 == 0:
            return 'Y'
        else:
            return 'N'
    else:
        return None

# not used
def lookupPileup(pileupDirL,sId,chrom,loc,ref,alt,flag='T'):

    inputFileNL = []

    if flag == 'T':
        for pileupDir in pileupDirL:
            inputFileNL += os.popen('find %s -name %s_T_*%s.pileup_proc' % (pileupDir,sId,chrom)).readlines()
    else:
        for pileupDir in pileupDirL:
            inputFileNL += os.popen('find %s -name %s_N_*%s.pileup_proc' % (pileupDir,sId,chrom)).readlines()
            inputFileNL += os.popen('find %s -name %s_B_*%s.pileup_proc' % (pileupDir,sId,chrom)).readlines()

    if len(inputFileNL) > 1:
        inputFileNL = [x for x in inputFileNL if not re.match('.*KN.*', x)]

    if len(inputFileNL) == 0:
        return None

    resultL = os.popen('grep -m 1 "^%s:%s," %s' % (chrom,loc,inputFileNL[0].rstrip()), 'r').readlines()

    if len(resultL)==0:
        return None
    else:
        tL = resultL[0].rstrip().split(',')
        if ref != tL[2]:
            sys.exit(1)
        refCount = int(tL[3])
        altCount = tL[4].count(alt)
        return (altCount,refCount)

# not used
def lookupPileup_batch(pileupDirL,chrom,loc,ref,alt,flag='T',useFlag=True):

    ## same critera as mutScan
    minCover = 3
    minMutReads = 2
    minFreq = 0.01

    inputFileNL = []

    if useFlag:
        if flag == 'T':
            for pileupDir in pileupDirL:
                inputFileNL += os.popen('find %s -name *_T_*%s.pileup_proc' % (pileupDir,chrom)).readlines()
        else:
            for pileupDir in pileupDirL:
                inputFileNL += os.popen('find %s -name *_N_*%s.pileup_proc' % (pileupDir,chrom)).readlines()
                inputFileNL += os.popen('find %s -name *_B_*%s.pileup_proc' % (pileupDir,chrom)).readlines()
    else:
        for pileupDir in pileupDirL:
            inputFileNL += os.popen('find %s -name *%s.pileup_proc' % (pileupDir,chrom)).readlines()
    
    if len(inputFileNL) > 1:
        inputFileNL = [x for x in inputFileNL if not re.match('.*KN.*', x)]
    
    if len(inputFileNL) == 0:
        return None
    
    resultH = {}
    for inputFile in inputFileNL:
        sampN = inputFile.rstrip().split('/')[-1].split('_')[0]
        resultL = os.popen('grep -m 1 -P "^%s\\t%s\\t" %s' % (chrom, loc, inputFile.rstrip()), 'r').readlines()

        if len(resultL) > 0:
            tL = resultL[0].rstrip().split('\t')
            tot = int(tL[3])
            altCount = tL[4].upper().count(alt)
            refCount = tot - altCount
            resultH[sampN] = '%s|%s' % (refCount, altCount)
        else:
            resultH[sampN] = 'NA'

    return resultH

# not used
def df_gtex_tpm():
    
    return pd.read_csv('%s/D/DB/gtex/GTEx_Analysis_2017-06-05_v8_RNASeQCv1.1.9_gene_median_tpm.gct.gz' % homedir,skiprows=2,sep='\t').iloc[:,1:].groupby('Description').median()

# not used
def df_exac():

    return pd.read_csv('%s/D/DB/exac/forweb_cleaned_exac_r03_march16_z_data_pLI.txt.gz' % homedir,sep='\t',dtype={'pLI':np.float}).iloc[:,1:].set_index('gene')

# not used
class tcgaCnaDB:

    def __init__(self,gctFileName):

        self.db= {}
        self.idx= {}

        inFile = open(gctFileName)

        inFile.readline(); inFile.readline()

        headerL = inFile.readline()[:-1].split('\t')

        for i in range(2,len(headerL)):
            self.idx[headerL[i]] = i-2

        for line in inFile:

            tokL = line[:-1].split('\t')
            self.db[tokL[0]] = tokL[2:]

    def query(self,sampN,geneN):

        if geneN in self.db and sampN in self.idx:
            return self.db[geneN][self.idx[sampN]]
        else:
            return ''

# not used
def parse_vcf_info(info):

    itemL = info.split(';')
    datH = {}

    for item in itemL:

        tag = item.split('=')[0]
        val = '='.join(item.split('=')[1:])

        if tag == 'GENE':

            rm = re.match('([^_]*)_?(ENS.[0-9]{11})',val)

            if rm:
                geneName = rm.group(1)
                ens_transID = rm.group(2)
                datH[tag] = (geneName,ens_transID)
            else:
                datH[tag] = (val,'')

        else:
            datH[tag] = val

    return(datH)

# not used
def getGenePos(refFlatFile, geneList=[]):
    inFile = open(refFlatFile, 'r')
    posH = {}
    for line in inFile:
        colL = line[:-1].split('\t')
        gene_sym = colL[0]
        chrom = colL[2]
        pos = int(colL[4])
        if geneList==[] or gene_sym in geneList:
            if gene_sym not in posH:
                posH[gene_sym] = {'chrom':chrom, 'pos':pos}
            elif posH[gene_sym]['pos'] > pos:
                posH[gene_sym]['pos'] = pos
    return posH

# not used
def loadCosmic(cosmicDat='/data1/Sequence/cosmic/cosmic.dat'):
    h = {}

    for line in open(cosmicDat):
        colL = line.rstrip().split('\t')
        chr_ = colL[0]
        sta = colL[1]
        end = colL[2]
        ref = colL[4]
        alt = colL[5]
        key = (chr_, sta, end, ref, alt)
        if key not in h:
            h[key] = 'Y'
    
    return h
