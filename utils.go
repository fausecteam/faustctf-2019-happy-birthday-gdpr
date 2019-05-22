package main

import "bytes"
import "unicode"

func assert(cond bool, msg interface{}) {
	if !cond {
		panic(msg)
	}
}

func check(err error) {
	assert(err == nil, err)
}

func isDigits(s string) bool {
	for _, c := range s {
		if !unicode.IsDigit(c) {
			return false
		}
	}
	return true
}

func makeUpper(data []byte) []byte {
	return append(data[:0], bytes.Map(unicode.ToUpper, data)...)
}

func trim(bs []byte) []byte {
	for i, b := range bs {
		if b == 0 {
			return bs[:i]
		}
	}
	return bs
}
