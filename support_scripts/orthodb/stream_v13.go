// Stream v13 gzip tables as app-compatible tab-separated records.
// Build with: go build -o stream_v13 stream_v13.go
package main

import (
	"bufio"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strconv"
	"strings"
)

func geneID(s string) (int64, error) {
	a := strings.Split(s, "_")
	if len(a) != 2 { return 0, fmt.Errorf("invalid gene id %q", s) }
	b := strings.Split(a[1], ":")
	if len(b) != 2 { return 0, fmt.Errorf("invalid gene id %q", s) }
	tax, err := strconv.ParseUint(a[0], 10, 31)
	if err != nil { return 0, err }
	org, err := strconv.ParseUint(b[0], 10, 8)
	if err != nil { return 0, err }
	gene, err := strconv.ParseUint(b[1], 16, 24)
	if err != nil { return 0, err }
	return int64(tax<<32 | org<<24 | gene), nil
}

func run() error {
	if len(os.Args) != 4 && len(os.Args) != 5 { return fmt.Errorf("usage: stream_v13 genes|memberships input.gz levels.csv [skip_emitted_records]") }
	var skip int64
	if len(os.Args) == 5 {
		var err error
		skip, err = strconv.ParseInt(os.Args[4], 10, 64)
		if err != nil || skip < 0 { return fmt.Errorf("invalid resume record count") }
	}
	levels := map[string]bool{}
	for _, level := range strings.Split(os.Args[3], ",") { levels[level] = true }
	file, err := os.Open(os.Args[2]); if err != nil { return err }; defer file.Close()
	z, err := gzip.NewReader(file); if err != nil { return err }; defer z.Close()
	r := bufio.NewReaderSize(z, 1024*1024)
	w := bufio.NewWriterSize(os.Stdout, 1024*1024)
	defer w.Flush()
	var rows, written, mappedSkipped int64
	xrefTypes := map[string]int64{}
	validationHits := map[string]int64{}
	for {
		line, readErr := r.ReadString('\n')
		if readErr != nil && readErr != io.EOF { return readErr }
		if len(line) > 0 {
			rows++
			fields := strings.Split(strings.TrimRight(line, "\r\n"), "\t")
			switch os.Args[1] {
			case "xrefs", "geneids":
				if len(fields) != 3 { return fmt.Errorf("xref row %d has %d columns", rows, len(fields)) }
				xrefTypes[fields[2]]++
				kind := ""
				if fields[2] == "UniProt" { kind = "U" }
				if fields[2] == "NCBIgenename" { kind = "N" }
				if os.Args[1] == "geneids" {
					kind = ""
					if fields[2] == "NCBIgid" { kind = "I" }
				}
				if kind == "" || strings.TrimSpace(fields[1]) == "" { break }
				if strings.HasPrefix(fields[0], "u_") { mappedSkipped++; break }
				id, e := geneID(fields[0]); if e != nil { return e }
				value := strings.TrimSpace(fields[1])
				if strings.HasPrefix(fields[0], "9606_") {
					switch value {
					case "Q9UL18", "Q92484", "P05026", "P06748", "AGO1", "SMPDL3A", "ATP1B1", "NPM1":
						validationHits[value]++
					}
				}
				written++
				if written > skip {
					if _, e = fmt.Fprintf(w, "%d\t%s\t%s\n", id, kind, value); e != nil { return e }
				}
			case "genes":
				if len(fields) < 8 { return fmt.Errorf("gene row %d has %d columns", rows, len(fields)) }
				// v13 mapped-only u_ IDs are outside the app's legacy packed-ID format.
				if strings.HasPrefix(fields[0], "u_") { mappedSkipped++; break }
				id, e := geneID(fields[0]); if e != nil { return e }
				if strings.TrimSpace(fields[4]) == "" && strings.TrimSpace(fields[6]) == "" { break }
				// UniProt accessions may have multiple mappings; preserve each.
				accessions := strings.FieldsFunc(fields[4], func(c rune) bool { return c == ';' || c == ',' })
				if len(accessions) == 0 { accessions = []string{""} }
				for _, accession := range accessions {
					written++
					if written <= skip { continue }
					if _, e = fmt.Fprintf(w, "%d\t%s\t%s\n", id, strings.TrimSpace(accession), strings.TrimSpace(fields[6])); e != nil { return e }
				}
			case "memberships":
				if len(fields) != 2 { return fmt.Errorf("membership row %d has %d columns", rows, len(fields)) }
				og := strings.Split(fields[0], "at")
				if len(og) != 2 { return fmt.Errorf("invalid group %q", fields[0]) }
				if !levels[og[1]] { break }
				if strings.HasPrefix(fields[1], "u_") { mappedSkipped++; break }
				cluster, e := strconv.ParseInt(og[0], 10, 64); if e != nil { return e }
				clade, e := strconv.ParseInt(og[1], 10, 64); if e != nil { return e }
				id, e := geneID(fields[1]); if e != nil { return e }
				written++
				if written > skip {
					if _, e = fmt.Fprintf(w, "%d\t%d\t%d\n", id, cluster, clade); e != nil { return e }
				}
			default: return fmt.Errorf("unknown mode %q", os.Args[1])
			}
			if rows % 10000000 == 0 { fmt.Fprintf(os.Stderr, "%s: %d source rows, %d emitted\n", os.Args[1], rows, written) }
		}
		if readErr == io.EOF { break }
	}
	if err = w.Flush(); err != nil { return err }
	if written < skip { return fmt.Errorf("resume count exceeds input records") }
	if path := os.Getenv("ORTHODB_STREAM_STATS"); path != "" {
		stats, err := json.Marshal(map[string]interface{}{"source_rows": rows, "compatible_records": written, "mapped_only_skipped": mappedSkipped, "xref_types": xrefTypes, "validation_hits": validationHits})
		if err != nil { return err }
		if err = os.WriteFile(path, stats, 0644); err != nil { return err }
	}
	fmt.Fprintf(os.Stderr, "%s complete: %d source rows, %d compatible records, %d mapped-only records excluded\n", os.Args[1], rows, written, mappedSkipped)
	return nil
}

func main() {
	if err := run(); err != nil { fmt.Fprintln(os.Stderr, err); os.Exit(1) }
}
