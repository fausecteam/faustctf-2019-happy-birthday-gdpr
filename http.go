package main

import (
	"github.com/jinzhu/gorm"
	"io/ioutil"
	"strconv"
	"strings"
)
import "fmt"
import "net/http"

const maxUploadSize = 256 * 1024 // 256 KiB

func initHttp() {
	http.HandleFunc("/", httpRoot)
	http.HandleFunc("/register", httpRegister)
	http.HandleFunc("/login", httpLogin)
	http.HandleFunc("/logout", httpLogout)
	http.HandleFunc("/account", httpAccount)
	http.HandleFunc("/upload", httpUpload)
	http.HandleFunc("/download", httpDownload)
	http.HandleFunc("/static/", httpStatic)
}

func httpRoot(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/" {
		username := ""
		if session := RequestSession(r); session != nil {
			username = session.Username()
		}
		w.Header().Set("Content-Type", "text/html")
		check(renderTemplate(w, "index.html", struct{ UserName string }{username}))
	} else if r.URL.Path == "/index.html" {
		http.Redirect(w, r, "/", http.StatusSeeOther)
	} else {
		http.NotFound(w, r)
	}
}

func httpRegister(w http.ResponseWriter, r *http.Request) {
	if RequestSession(r) != nil {
		http.Redirect(w, r, "/account", http.StatusTemporaryRedirect)
	}

	errorMessage := ""
	if r.Method == "POST" {
		err := registerUser(r.FormValue("username"), r.FormValue("password"))
		if err != nil {
			errorMessage = err.Error()
		} else {
			http.Redirect(w, r, "/login", http.StatusTemporaryRedirect)
			return
		}
	}
	w.Header().Set("Content-Type", "text/html")
	check(renderTemplate(w, "register.html", struct {
		UserName     string
		ErrorMessage string
	}{"", errorMessage}))
}

func httpLogin(w http.ResponseWriter, r *http.Request) {
	if RequestSession(r) != nil {
		http.Redirect(w, r, "/account", http.StatusTemporaryRedirect)
	}

	if r.Method == "GET" {
		w.Header().Set("Content-Type", "text/html")
		check(renderTemplate(w, "login.html", struct{ UserName string }{""}))
	} else if r.Method == "POST" {
		username := r.FormValue("username")
		password := r.FormValue("password")
		username = string(makeUpper([]byte(username)))
		var user User
		if result := db.Where(&User{Username: username}).First(&user); result.Error != nil {
			http.Redirect(w, r, "/login", http.StatusSeeOther)
			return
		}
		session := NewSession()
		copy(session.UsernameBytes(), username)
		copy(session.PasswordBytes(), password)
		session.SetUid(uint64(user.ID))
		http.SetCookie(w, session.ToCookie())
		http.Redirect(w, r, "/account", http.StatusSeeOther)
	}
}

func httpLogout(w http.ResponseWriter, r *http.Request) {
	http.SetCookie(w, &http.Cookie{Name: "session"})
	http.Redirect(w, r, "/", http.StatusSeeOther)
}

func httpAccount(w http.ResponseWriter, r *http.Request) {
	session := RequestSession(r)
	if session == nil {
		http.Redirect(w, r, "/login", http.StatusSeeOther)
		return
	}

	var files []File
	db.Where(&File{UserId: uint(session.Uid())}).Find(&files)

	userRecord := User{Model: gorm.Model{ID: uint(session.Uid())}}
	db.Where(&userRecord).Find(&userRecord)

	w.Header().Set("Content-Type", "text/html")
	check(renderTemplate(w, "account.html", struct {
		UserName   string
		UserRecord User
		Files      []File
	}{session.Username(), userRecord, files}))
}

func httpUpload(w http.ResponseWriter, r *http.Request) {
	session := RequestSession(r)
	if session == nil {
		http.Redirect(w, r, "/login", http.StatusSeeOther)
		return
	}

	errorMessage := ""
	successMessage := ""
	if r.Method == "POST" {
		r.Body = http.MaxBytesReader(w, r.Body, maxUploadSize)
		if err := r.ParseMultipartForm(maxUploadSize); err != nil {
			if err.Error() == "http: request body too large" {
				errorMessage = fmt.Sprintf("Uploaded file is too large.")
				goto out
			} else {
				panic(err)
			}
		}

		username := r.FormValue("user")
		var user User
		if userid, err := strconv.ParseUint(username, 10, 0); err == nil {
			user.ID = uint(userid)
		} else {
			user.Username = string(makeUpper([]byte(username)))
		}
		if result := db.Where(&user).First(&user); result.Error != nil {
			errorMessage = fmt.Sprintf("unknown user %q\n", username)
			goto out
		}

		file, header, err := r.FormFile("data")
		if err != nil {
			errorMessage = "cannot read uploaded file"
			goto out
		}
		data, err := ioutil.ReadAll(file)
		if err != nil {
			errorMessage = "cannot read uploaded file"
			goto out
		}

		fileRecord := File{
			UserId:   user.ID,
			Name:     header.Filename,
			MimeType: header.Header.Get("Content-Type"),
			Data:     data,
		}
		if result := db.Create(&fileRecord); result.Error != nil {
			errorMessage = "Failed to save upload."
			goto out
		}

		successMessage = "File uploaded successfully."
		goto out
	}
out:
	w.Header().Set("Content-Type", "text/html")
	check(renderTemplate(w, "upload.html", struct {
		UserName       string
		ErrorMessage   string
		SuccessMessage string
	}{session.Username(), errorMessage, successMessage}))
}

func httpDownload(w http.ResponseWriter, r *http.Request) {
	session := RequestSession(r)
	if session == nil {
		http.Redirect(w, r, "/login", http.StatusSeeOther)
		return
	}

	fileId, err := strconv.Atoi(r.URL.RawQuery)
	if err != nil {
		fileId = -1
	}

	var file File
	if result := db.Where(&File{Model: gorm.Model{ID: uint(fileId)}, UserId: uint(session.Uid())}).First(&file); result.Error != nil {
		w.WriteHeader(http.StatusNotFound)
		fmt.Fprintln(w, "file not found")
		return
	}

	if file.MimeType == "" {
		file.MimeType = "application/octet-stream"
	}
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=%s", file.Name))
	w.Header().Set("Content-Type", file.MimeType)
	w.Write(file.Data)
}

func httpStatic(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Path[1:]
	data, ok := bindata[name]
	if !ok {
		w.WriteHeader(http.StatusNotFound)
		fmt.Fprintln(w, "file not found")
		return
	}
	mimeType := "application/octet-stream"
	if strings.HasSuffix(name, ".css") {
		mimeType = "text/css"
	}
	w.Header().Set("Content-Type", mimeType)
	w.Write([]byte(data))
}
