package main

import (
	"flag"
	"net/http"
)

var flagListen string
var flagStorage string
var flagDatabaseType string
var flagDatabaseConnect string

func main() {
	flag.StringVar(&flagListen, "listen", ":4377", "'address:port' to listen on")
	flag.StringVar(&flagStorage, "storage", "./data", "persistent storage directory")
	flag.StringVar(&flagDatabaseType, "database-type", "", "database type (sqlite3 or postgres)")
	flag.StringVar(&flagDatabaseConnect, "database-connect", "", "database to connect to, see http://gorm.io/docs/connecting_to_the_database.html")
	flag.Parse()

	initDatabase()
	initHttp()

	err := http.ListenAndServe(flagListen, nil)
	if err != nil {
		panic(err)
	}
}
