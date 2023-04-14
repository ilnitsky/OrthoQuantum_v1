package main

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"os"
	"strconv"
	"syscall"

	"github.com/vbauerster/mpb/v7"
	"github.com/vbauerster/mpb/v7/decor"
)

// CGO_ENABLED=0 GOOS=linux GOARCH=amd64 GOAMD64=v1 go build -ldflags="-s -w" -trimpath -a
/*
./tabprocessor gene_xrefs other/odb11v0_gene_xrefs.tab
 && ./tabprocessor gene_names odb11v0_genenames_all.tab && ./tabprocessor OG2genes odb11v0_OG2genes.tab

sqlite3 orthodb.db <./scripts/1_uniprot.sql && sqlite3 orthodb.db <./scripts/2_gene_names.sql && sqlite3 orthodb.db <./scripts/3_OG.sql
*/

const fifo_file = "/tmp/import_data.tab"

func prepare_progress(size int64) *mpb.Bar {
	p := mpb.New()

	name := "Importing:"
	// adding a single bar, which will inherit container's width
	bar := p.AddBar(size,
		mpb.PrependDecorators(
			// display our name with one space on the right
			decor.Name(name, decor.WC{W: len(name) + 1, C: decor.DidentRight}),
			// replace ETA decorator with "done" message, OnComplete event
			decor.OnComplete(
				decor.AverageETA(decor.ET_STYLE_MMSS, decor.WC{W: 4}), "done",
			),
		),
		mpb.AppendDecorators(decor.NewPercentage("% .2f")),
	)
	return bar
}

func do() error {
	if len(os.Args) != 3 {
		return fmt.Errorf("usage: file_kind *.tab_file")
	}
	fileKind := os.Args[1]
	filePath := os.Args[2]
	cladesWhitelist := map[int]struct{}{
		2759:      struct{}{},
		2763:      struct{}{},
		2836:      struct{}{},
		3041:      struct{}{},
		3166:      struct{}{},
		3193:      struct{}{},
		3646:      struct{}{},
		3699:      struct{}{},
		3744:      struct{}{},
		3745:      struct{}{},
		4069:      struct{}{},
		4085:      struct{}{},
		4143:      struct{}{},
		4447:      struct{}{},
		4751:      struct{}{},
		4761:      struct{}{},
		4762:      struct{}{},
		4764:      struct{}{},
		4783:      struct{}{},
		4827:      struct{}{},
		4890:      struct{}{},
		4891:      struct{}{},
		4893:      struct{}{},
		5042:      struct{}{},
		5052:      struct{}{},
		5073:      struct{}{},
		5125:      struct{}{},
		5129:      struct{}{},
		5139:      struct{}{},
		5178:      struct{}{},
		5204:      struct{}{},
		5206:      struct{}{},
		5257:      struct{}{},
		5303:      struct{}{},
		5317:      struct{}{},
		5338:      struct{}{},
		5529:      struct{}{},
		5583:      struct{}{},
		5658:      struct{}{},
		5690:      struct{}{},
		5794:      struct{}{},
		5796:      struct{}{},
		5800:      struct{}{},
		5806:      struct{}{},
		5809:      struct{}{},
		5820:      struct{}{},
		5863:      struct{}{},
		5864:      struct{}{},
		5878:      struct{}{},
		6029:      struct{}{},
		6073:      struct{}{},
		6101:      struct{}{},
		6231:      struct{}{},
		6447:      struct{}{},
		6656:      struct{}{},
		6657:      struct{}{},
		6854:      struct{}{},
		6893:      struct{}{},
		6933:      struct{}{},
		6960:      struct{}{},
		7041:      struct{}{},
		7088:      struct{}{},
		7147:      struct{}{},
		7148:      struct{}{},
		7157:      struct{}{},
		7164:      struct{}{},
		7203:      struct{}{},
		7214:      struct{}{},
		7215:      struct{}{},
		7393:      struct{}{},
		7399:      struct{}{},
		7434:      struct{}{},
		7524:      struct{}{},
		7742:      struct{}{},
		7898:      struct{}{},
		8457:      struct{}{},
		8509:      struct{}{},
		8782:      struct{}{},
		8948:      struct{}{},
		9108:      struct{}{},
		9126:      struct{}{},
		9205:      struct{}{},
		9263:      struct{}{},
		9347:      struct{}{},
		9362:      struct{}{},
		9443:      struct{}{},
		9604:      struct{}{},
		9721:      struct{}{},
		9989:      struct{}{},
		13792:     struct{}{},
		27994:     struct{}{},
		28556:     struct{}{},
		28568:     struct{}{},
		28738:     struct{}{},
		32523:     struct{}{},
		33090:     struct{}{},
		33183:     struct{}{},
		33208:     struct{}{},
		33392:     struct{}{},
		33554:     struct{}{},
		33630:     struct{}{},
		33634:     struct{}{},
		34365:     struct{}{},
		34379:     struct{}{},
		34384:     struct{}{},
		34395:     struct{}{},
		34397:     struct{}{},
		34735:     struct{}{},
		36668:     struct{}{},
		37572:     struct{}{},
		37989:     struct{}{},
		38820:     struct{}{},
		40674:     struct{}{},
		41084:     struct{}{},
		41938:     struct{}{},
		50557:     struct{}{},
		68889:     struct{}{},
		71240:     struct{}{},
		72025:     struct{}{},
		75966:     struct{}{},
		91561:     struct{}{},
		92860:     struct{}{},
		93133:     struct{}{},
		110618:    struct{}{},
		115784:    struct{}{},
		119089:    struct{}{},
		142796:    struct{}{},
		147541:    struct{}{},
		147545:    struct{}{},
		147548:    struct{}{},
		147550:    struct{}{},
		155616:    struct{}{},
		155619:    struct{}{},
		162481:    struct{}{},
		162484:    struct{}{},
		231213:    struct{}{},
		299071:    struct{}{},
		300275:    struct{}{},
		314145:    struct{}{},
		314146:    struct{}{},
		314147:    struct{}{},
		314294:    struct{}{},
		314295:    struct{}{},
		422676:    struct{}{},
		474942:    struct{}{},
		474943:    struct{}{},
		490731:    struct{}{},
		554915:    struct{}{},
		766764:    struct{}{},
		1028384:   struct{}{},
		1156497:   struct{}{},
		1206795:   struct{}{},
		1286322:   struct{}{},
		1489911:   struct{}{},
		1535326:   struct{}{},
		1549675:   struct{}{},
		1913637:   struct{}{},
		199999999: struct{}{},
	}
	inputFile, err := os.Open(filePath)
	if err != nil {
		return fmt.Errorf("Can't open file: %w", err)
	}
	defer inputFile.Close()

	stat, err := inputFile.Stat()
	if err != nil {
		return fmt.Errorf("Can't stat file: %w", err)
	}

	_ = os.Remove(fifo_file) // best-effort delete

	err = syscall.Mkfifo(fifo_file, 0o600)
	if err != nil {
		return fmt.Errorf("Can't mkfifo: %w", err)
	}
	defer os.Remove(fifo_file)

	fmt.Printf("Start import from file %s\n", fifo_file)

	outputFile, err := os.OpenFile(fifo_file, os.O_WRONLY, 0600)
	if err != nil {
		return fmt.Errorf("Can't open pipe: %w", err)
	}
	defer outputFile.Close()

	bar := prepare_progress(stat.Size())
	r := bufio.NewReader(bar.ProxyReader(inputFile))

	w := bufio.NewWriter(outputFile)
	defer w.Flush()
	defer fmt.Print("\n")
	switch fileKind {
	case "gene_xrefs":
		var expected_source []byte
		expected_source = []byte("UniProt")
		for {
			line, err := r.ReadBytes('\n')
			switch err {
			case nil:
				// continue processing
			case io.EOF:
				return nil
			default:
				return fmt.Errorf("Read error: %w", err)
			}

			parts, err := splitter(line, "_", ":", "\t", "\t")
			if err != nil {
				return fmt.Errorf("Error processing line \"%s\": %w", line, err)
			}

			xref, xref_source := parts[3], parts[4]
			if !bytes.Equal(xref_source, expected_source) {
				continue
			}

			gid, err := geneIDToInt(parts[0], parts[1], parts[2])
			if err != nil {
				return fmt.Errorf("GeneID parsing error error \"%s\": %w", line, err)
			}

			w.WriteString(strconv.FormatInt(gid, 10)) //nolint:errcheck
			w.WriteByte('\t')                         //nolint:errcheck
			w.Write(bytes.TrimSpace(xref))            //nolint:errcheck
			err = w.WriteByte('\n')
			if err != nil {
				return fmt.Errorf("Write error \"%s\": %w", line, err)
			}
		}
	case "gene_names":
		for {
			line, err := r.ReadBytes('\n')
			switch err {
			case nil:
				// continue processing
			case io.EOF:
				return nil
			default:
				return fmt.Errorf("Read error: %w", err)
			}
			if bytes.HasPrefix(line, []byte("u_")) {
				fmt.Fprintf(os.Stderr, "Incorrect format %s", line)
				continue
			}

			parts, err := splitter(line, "_", ":", "\t")
			if err != nil {
				return fmt.Errorf("Error processing line \"%s\": %w", line, err)
			}

			gene_name := parts[3]

			gid, err := geneIDToInt(parts[0], parts[1], parts[2])
			if err != nil {
				return fmt.Errorf("GeneID parsing error error \"%s\": %w", line, err)
			}

			w.WriteString(strconv.FormatInt(gid, 10)) //nolint:errcheck
			w.WriteByte('\t')                         //nolint:errcheck
			w.Write(bytes.TrimSpace(gene_name))       //nolint:errcheck
			err = w.WriteByte('\n')
			if err != nil {
				return fmt.Errorf("Write error \"%s\": %w", line, err)
			}
		}
	case "OG2genes":
	loop:
		for {
			line, err := r.ReadBytes('\n')
			switch err {
			case nil:
				// continue processing
			case io.EOF:
				return nil
			default:
				return fmt.Errorf("Read error: %w", err)
			}

			parts, err := splitter(line, "at", "\t", "_", ":")
			if err != nil {
				return fmt.Errorf("Error processing line \"%s\": %w", line, err)
			}
			clusterID, clade := parts[0], parts[1]
			i, err := strconv.Atoi(string(clade))
			if err != nil {
				fmt.Fprintf(os.Stderr, "Non-numeric clade: %s", string(clade))
				continue loop
			}
			_, found := cladesWhitelist[i]
			if !found {
				continue loop
			}

			gid, err := geneIDToInt(parts[2], parts[3], parts[4])
			if err != nil {
				return fmt.Errorf("GeneID parsing error error \"%s\": %w", line, err)
			}

			w.WriteString(strconv.FormatInt(gid, 10)) //nolint:errcheck
			w.WriteByte('\t')                         //nolint:errcheck
			w.Write(clusterID)                        //nolint:errcheck
			w.WriteByte('\t')                         //nolint:errcheck
			w.Write(clade)                            //nolint:errcheck
			err = w.WriteByte('\n')
			if err != nil {
				return fmt.Errorf("Write error \"%s\": %w", line, err)
			}
		}

	default:
		return fmt.Errorf("Unknown file kind: %s", fileKind)
	}

}

// orthodb_id = orthodb_id.strip()
// a, c = orthodb_id.split(":", maxsplit=1)
// a, b = a.split("_", maxsplit=1)
// return (((int(a) << B_LEN) | int(b)) << C_LEN) | int(c, 16)

func geneIDToInt(part1, part2, part3 []byte) (int64, error) {
	a, err := strconv.ParseInt(string(part1), 10, 32)
	if err != nil {
		return 0, fmt.Errorf(`Incorrect geneId.part1 format: "%s" %w`, part1, err)
	}

	b, err := strconv.ParseInt(string(part2), 10, 32)
	if err != nil || b > 0xFF {
		return 0, fmt.Errorf(`Incorrect geneId.part2 format: "%s" %w`, part2, err)
	}

	c, err := strconv.ParseInt(string(part3), 16, 32)
	if err != nil || c > 0xFFFFFF {
		return 0, fmt.Errorf(`Incorrect geneId.part3 format: "%s" %w`, part3, err)
	}
	return (a << (32)) | (b << 24) | c, nil
}

func splitter(src []byte, delims ...string) (splits [][]byte, err error) {
	splits = make([][]byte, len(delims)+1)
	for i, delim := range delims {
		idx := bytes.Index(src, []byte(delim))
		if idx == -1 {
			return nil, fmt.Errorf(`Delimiter #%d ("%s") not found`, i, delim)
		}
		splits[i] = bytes.TrimSpace(src[:idx])
		src = src[idx+len(delim):]
	}
	splits[len(splits)-1] = bytes.TrimSpace(src)
	return
}

func intToGeneID(geneID int64) string {
	return fmt.Sprintf(
		"%d_%d:%06x",
		geneID>>32,
		(geneID>>24)&0xFF,
		geneID&0xFFFFFF,
	)
}

func main() {
	// res, err := geneIDToInt([]byte("10340373_90:0000FF"))
	// if err != nil {
	// 	panic(err)
	// }

	// fmt.Println(res)
	err := do()
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s\n", err)
		os.Exit(1)
	}
}
