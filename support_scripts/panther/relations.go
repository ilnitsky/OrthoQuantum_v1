// Stream PANTHER v19 tar.gz relationships as normalized integer-key records.
package main
import("archive/tar";"bufio";"compress/gzip";"encoding/json";"fmt";"io";"os";"path/filepath";"strconv";"strings")
func canonical(s string)(string,string,string,error){
 parts:=strings.Split(s,"|");if len(parts)<2||parts[0]==""{return "","","",fmt.Errorf("invalid PANTHER gene id %q",s)}
 up:="";for _,p:=range parts[1:]{if strings.HasPrefix(p,"UniProtKB="){up=strings.TrimPrefix(p,"UniProtKB=")}}
 if up==""{return "","","",fmt.Errorf("missing UniProtKB in %q",s)}
 return parts[0]+"|"+up,parts[0],up,nil
}
func run()error{
 if len(os.Args)<5{return fmt.Errorf("usage: panther_relations gene_keys.tsv metadata.json AllOrthologs.tar.gz AllParalogs.tar.gz")}
 keys:=map[string]int64{};var next int64
 seed,e:=os.Open(os.Args[1]);if e!=nil{return e};scan:=bufio.NewScanner(seed);scan.Buffer(make([]byte,65536),1024*1024)
 for scan.Scan(){f:=strings.SplitN(scan.Text(),"\t",3);if len(f)<2{return fmt.Errorf("invalid gene seed")};id,e:=strconv.ParseInt(f[0],10,64);if e!=nil{return e};keys[strings.Clone(f[1])]=id;if id>next{next=id}}
 if e=scan.Err();e!=nil{return e};seed.Close()
 ancestors:=map[string]int64{};families:=map[string]int64{};types:=map[string]int64{};counts:=map[string]int64{};var unknown,rows int64
 output:=bufio.NewWriterSize(os.Stdout,1024*1024)
 index:=func(m map[string]int64,s string)int64{id,ok:=m[s];if !ok{id=int64(len(m)+1);m[strings.Clone(s)]=id};return id}
 gene:=func(raw string)(int64,error){key,genome,up,err:=canonical(raw);if err!=nil{return 0,err};if id,ok:=keys[key];ok{return id,nil};next++;keys[key]=next;unknown++;_,err=fmt.Fprintf(output,"G\t%d\t%s\t%s\t%s\n",next,genome,up,raw);return next,err}
 for _,archive:=range os.Args[3:]{
  name:=strings.TrimSuffix(filepath.Base(archive),".tar.gz");if name!="AllOrthologs"&&name!="AllParalogs"{return fmt.Errorf("unexpected archive %q",name)}
  f,err:=os.Open(archive);if err!=nil{return err};z,err:=gzip.NewReader(f);if err!=nil{return err};t:=tar.NewReader(z);members:=0
  for{h,err:=t.Next();if err==io.EOF{break};if err!=nil{return err};if !h.FileInfo().Mode().IsRegular(){continue};if filepath.Base(h.Name)!=name{return fmt.Errorf("unexpected tar member %q",h.Name)};members++
   r:=bufio.NewReaderSize(t,1024*1024)
   for{line,readErr:=r.ReadString('\n');if readErr!=nil&&readErr!=io.EOF{return readErr};line=strings.TrimRight(line,"\r\n")
    if line!=""{fields:=strings.Split(line,"\t");if len(fields)!=5{return fmt.Errorf("%s row %d: expected 5 columns, got %d",name,counts[name]+1,len(fields))}
     kind:=fields[2];if (name=="AllOrthologs"&&kind!="LDO"&&kind!="O")||(name=="AllParalogs"&&kind!="P"){return fmt.Errorf("unexpected relation %q in %s",kind,name)}
     a,err:=gene(fields[0]);if err!=nil{return err};b,err:=gene(fields[1]);if err!=nil{return err}
     if fields[3]==""||!strings.HasPrefix(fields[4],"PTHR"){return fmt.Errorf("missing ancestor/family")}
     ancestor:=index(ancestors,fields[3]);family:=index(families,fields[4]);if _,err=fmt.Fprintf(output,"R\t%d\t%d\t%s\t%d\t%d\n",a,b,kind,ancestor,family);err!=nil{return err}
     rows++;counts[name]++;types[kind]++;if rows%5000000==0{output.Flush();fmt.Fprintf(os.Stderr,"relationships: %d rows streamed (%s)\n",rows,name)}
    };if readErr==io.EOF{break}
   }
  }
  if members!=1{return fmt.Errorf("expected one data member in %s",archive)}
  // Drain gzip after the tar EOF so the gzip CRC/trailer is actually checked.
  if _,err=io.Copy(io.Discard,z);err!=nil{return err};z.Close();f.Close()
 }
 if e=output.Flush();e!=nil{return e}
 data,e:=json.Marshal(map[string]interface{}{"rows":rows,"archives":counts,"types":types,"ancestors":ancestors,"families":families,"extra_genes":unknown,"genes":len(keys)});if e!=nil{return e}
 return os.WriteFile(os.Args[2],data,0644)
}
func main(){if e:=run();e!=nil{fmt.Fprintln(os.Stderr,e);os.Exit(1)}}
