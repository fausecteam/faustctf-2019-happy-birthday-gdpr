package main

import (
	"crypto/sha512"
	"fmt"
)

func registerUser(username string, password string) error {
	if len(username) > usernameLen {
		return fmt.Errorf("username must not be longer than %d characters", usernameLen)
	} else if isDigits(username) {
		return fmt.Errorf("username must contain at least one letter")
	} else if len(password) < 8 {
		return fmt.Errorf("sorry, but %q is not a secure password", password)
	} else if len(password) > passwordLen {
		return fmt.Errorf("password must not be longer than %d charachters", passwordLen)
	}

	tempSession := NewSession()
	copy(tempSession.UsernameBytes(), username)
	copy(tempSession.PasswordBytes(), password)
	makeUpper(tempSession.UsernameBytes())
	makeUpper(tempSession.PasswordBytes())
	passwordHash := sha512.Sum512(tempSession.PasswordBytesToHash())

	user := User{
		Username:     string(tempSession.UsernameBytes()[:len(username)]),
		PasswordHash: passwordHash[:],
	}
	if result := db.Create(&user); result.Error != nil {
		return fmt.Errorf("username %q is already taken", username)
	}
	return nil
}
