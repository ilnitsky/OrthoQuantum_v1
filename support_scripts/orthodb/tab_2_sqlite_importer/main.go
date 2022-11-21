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
	case "gene_xrefs", "gene_xrefs_names":
		var expected_source []byte
		switch fileKind {
		case "gene_xrefs":
			expected_source = []byte("UniProt")
		case "gene_xrefs_names":
			expected_source = []byte("NCBIgenename")
		}
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

			switch string(clade) {
			case "2759", "4751", "7742", "7898", "8782", "33090", "33208", "199999999":
			default:
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
