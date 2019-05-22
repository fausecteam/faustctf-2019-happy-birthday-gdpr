package main

import (
	"bytes"
	"flag"
	"fmt"
	"go/format"
	"io"
	"io/ioutil"
	"os"
	"path/filepath"
)

func check(err error) {
	if err != nil {
		panic(err)
	}
}

func main() {
	p := flag.String("p", "main", "go package name")
	o := flag.String("o", "", "output file name")
	v := flag.String("v", "bindata", "variable name")
	flag.Parse()

	b := bytes.NewBuffer(nil)
	_, err := fmt.Fprintf(b, "package %s\n\nvar %s = map[string]string{\n", *p, *v)
	check(err)
	for _, x := range flag.Args() {
		matches, err := filepath.Glob(x)
		check(err)
		for _, m := range matches {
			data, err := ioutil.ReadFile(m)
			check(err)
			_, err = fmt.Fprintf(b, "\t%q: %q,\n", m, data)
			check(err)
		}
	}
	_, err = fmt.Fprintf(b, "}\n")
	check(err)

	var f io.Writer
	if *o != "" {
		fp, err := os.Create(*o)
		check(err)
		defer func() { check(fp.Close()) }()
		f = fp
	} else {
		f = os.Stdout
	}

	c, err := format.Source(b.Bytes())
	check(err)
	_, err = f.Write(c)
	check(err)
}
