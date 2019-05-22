package main

import (
	"bytes"
	"io/ioutil"
	"os"
	"reflect"
	"unicode"
)

func main() {
	input, err := ioutil.ReadAll(os.Stdin)
	check(err)
	result := make([]byte, 0, len(input)*8)
	result = append(result, input...)
	var retval []byte
	switch os.Args[1] {
	case "lower":
		retval = append(result[:0], bytes.Map(unicode.ToLower, result)...)
	case "upper":
		retval = makeUpper(result)
	default:
		panic("invalid argument")
	}
	if !reflect.DeepEqual(retval, result) {
		panic("makeLower reallocated")
	}
	_, err = os.Stdout.Write(result)
	check(err)
}
