package main

import (
	"crypto/aes"
	"crypto/rand"
	"crypto/sha512"
	"crypto/subtle"
	"fmt"
	"math"
	"os"
	"strconv"
)
import "crypto/cipher"
import "encoding/base64"
import "net/http"

const (
	usernameIdx = 0
	usernameLen = 64
	passwordIdx = usernameIdx + usernameLen
	passwordLen = 64
	uidIdx      = passwordIdx + passwordLen
	uidLen      = 16
	sessionLen  = uidLen + uidIdx
)

type Session [sessionLen]byte

func NewSession() *Session {
	return &Session{}
}

func (s *Session) UsernameBytes() []byte {
	return s[usernameIdx : usernameIdx+usernameLen]
}

func (s *Session) Username() string {
	return string(trim(s.UsernameBytes()))
}

func (s *Session) PasswordBytes() []byte {
	return s[passwordIdx : passwordIdx+passwordLen]
}

func (s *Session) Password() string {
	return string(trim(s.PasswordBytes()))
}

func (s *Session) PasswordBytesToHash() []byte {
	assert(usernameIdx+usernameLen == passwordIdx, "invalid session format")
	return s[usernameIdx : passwordIdx+passwordLen]
}

func (s *Session) Uid() uint64 {
	uid, _ := strconv.ParseUint(string(s[uidIdx:uidIdx+uidLen]), 16, 64)
	if uid == 0 {
		return math.MaxUint64
	}
	return uid
}

func (s *Session) SetUid(uid uint64) {
	copy(s[uidIdx:uidIdx+uidLen], []byte(fmt.Sprintf("%016X", uid)))
}

func (s *Session) ToCookie() *http.Cookie {
	block, err := aes.NewCipher(sessionKey[:32])
	if err != nil {
		panic(err)
	}
	mode := cipher.NewCBCEncrypter(block, sessionKey[32:])
	cipher := make([]byte, sessionLen)
	mode.CryptBlocks(cipher, s[:])
	return &http.Cookie{
		Name:  "session",
		Value: base64.StdEncoding.EncodeToString(cipher),
	}
}

func (s *Session) Validate() bool {
	var user User
	if err := db.First(&user, s.Uid()).Error; err != nil {
		fmt.Println("Error: User not found", err, s.Uid())
		return false
	}

	makeUpper(s.UsernameBytes())
	makeUpper(s.PasswordBytes())
	candidatePasswordHash := sha512.Sum512(s.PasswordBytesToHash())

	return subtle.ConstantTimeCompare(user.PasswordHash, candidatePasswordHash[:]) == 1
}

func RequestSession(r *http.Request) *Session {
	cookie, err := r.Cookie("session")
	if err != nil {
		return nil
	}
	session := NewSession()
	n, err := base64.StdEncoding.Decode(session[:], []byte(cookie.Value))
	if err != nil || n != len(session) {
		return nil
	}
	block, err := aes.NewCipher(sessionKey[:32])
	if err != nil {
		panic(err)
	}
	mode := cipher.NewCBCDecrypter(block, sessionKey[32:])
	mode.CryptBlocks(session[:], session[:])
	if !session.Validate() {
		return nil
	}
	return session
}

var sessionKey = generateSessionKey()

func generateSessionKey() []byte {
	key := make([]byte, 32+16)
	if os.Getenv("HAPPY_BIRTHDAY_GDPR_SESSION") == "insecure" {
		fmt.Println("warning: using insecure session key")
	} else {
		_, err := rand.Read(key)
		check(err)
	}
	return key
}
