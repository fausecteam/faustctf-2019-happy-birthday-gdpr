package main

import (
	"github.com/jinzhu/gorm"
	_ "github.com/jinzhu/gorm/dialects/postgres"
	_ "github.com/jinzhu/gorm/dialects/sqlite"
)

type User struct {
	gorm.Model
	Username     string `gorm:"unique;size:64"`
	PasswordHash []byte `gorm:"size:64"`
}

type File struct {
	gorm.Model
	UserId   uint
	User     User
	Name     string
	MimeType string `gorm:"size:64"`
	Data     []byte
}

var db *gorm.DB

func initDatabase() {
	var err error
	db, err = gorm.Open(flagDatabaseType, flagDatabaseConnect)
	if err != nil {
		panic(err)
	}

	db.AutoMigrate(&User{})
	db.AutoMigrate(&File{})
}
