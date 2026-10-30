package main

import (
	"encoding/json"
	"os"

	"github.com/OpenNHP/opennhp/nhp/core"
)

// Scheme 0 only. This is OpenNHP's NewECDH(ECC_CURVE25519), the same call
// nhp-acd/nhp-serverd/nhp-relayd make for `keygen --curve`. It does not
// implement a curve. Args are accepted so the wrapper can pass the daemon
// flags; they are not a second generator.
func main() {
	e := core.NewECDH(core.ECC_CURVE25519)
	if e == nil {
		os.Exit(1)
	}
	_ = json.NewEncoder(os.Stdout).Encode(map[string]string{
		"privateKey": e.PrivateKeyBase64(),
		"publicKey":  e.PublicKeyBase64(),
	})
}
