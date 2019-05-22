package main

import (
	"bytes"
	"html/template"
	"io"
)

var templates *template.Template

func renderTemplate(wr io.Writer, name string, data interface{}) error {
	const prefix = "templates/"
	tmpl := template.New(name)
	tmpl.Funcs(template.FuncMap{
		"mod": func(i, j int) int {
			return i % j
		},
	})
	tmpl, err := tmpl.Parse(bindata[prefix+name])
	check(err)
	for {
		extendsTmpl, err := tmpl.Lookup("extends").Clone()
		check(err)
		if extendsTmpl == nil {
			break
		}
		extendsBuf := bytes.NewBuffer(nil)
		err = extendsTmpl.Execute(extendsBuf, nil)
		check(err)
		extends := extendsBuf.String()
		if tmpl.Lookup(extends) != nil {
			break
		}
		tmpl, err = tmpl.New(extends).Parse(bindata[prefix+extends])
		check(err)
	}
	return tmpl.Execute(wr, data)
}
