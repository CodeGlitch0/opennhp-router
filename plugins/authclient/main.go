package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"sync"

	"github.com/OpenNHP/opennhp/nhp/common"
	"github.com/OpenNHP/opennhp/nhp/plugins"
	toml "github.com/pelletier/go-toml/v2"
)

// authURL is the auth service on the host loopback. Compose DNS names do not resolve.
// Signatures match nhp/plugins/serverpluginhandler.go:
//
//	Init(*plugins.PluginParamsIn) error
//	AuthWithNHP(*common.NhpAuthRequest, *plugins.NhpServerPluginHelper) (*common.ServerKnockAckMsg, error)
//
// Hostname (the ACK name) and Addr.Ip (the address NHP-AC opens) are
// different upstream fields. This plugin does not put a backend address
// in either field.
const authURL = "http://127.0.0.1:8090/authorize"

const aspID = "authclient"

var (
	resourceMu  sync.Mutex
	resourceMap common.ResourceGroupMap
)

func Init(in *plugins.PluginParamsIn) error {
	dir := ""
	if in != nil && in.PluginDirPath != nil {
		dir = *in.PluginDirPath
	}
	content, err := os.ReadFile(filepath.Join(dir, "etc", "resource.toml"))
	if err != nil {
		return err
	}
	parsed := make(common.ResourceGroupMap)
	if err := toml.Unmarshal(content, &parsed); err != nil {
		return err
	}
	for resID, res := range parsed {
		if res == nil {
			continue
		}
		res.AuthServiceId = aspID
		res.ResourceId = resID
	}
	resourceMu.Lock()
	resourceMap = parsed
	resourceMu.Unlock()
	return nil
}

func AuthWithNHP(req *common.NhpAuthRequest, helper *plugins.NhpServerPluginHelper) (*common.ServerKnockAckMsg, error) {
	ack := &common.ServerKnockAckMsg{}
	if req != nil && req.Ack != nil {
		ack = req.Ack
	}
	if req == nil || req.Msg == nil {
		return deny(ack, common.ErrResourceNotFound)
	}
	if helper == nil {
		return ack, fmt.Errorf("AuthWithNHP: helper is null")
	}

	resourceMu.Lock()
	res, found := resourceMap[req.Msg.ResourceId]
	resourceMu.Unlock()
	if !found || res == nil || len(res.Resources) == 0 {
		return deny(ack, common.ErrResourceNotFound)
	}

	allowed, err := postAuthorize(req.PublicKey)
	if err != nil {
		ack.ErrCode = common.ErrHttpRequestFailed.ErrorCode()
		ack.ErrMsg = err.Error()
		return ack, err
	}
	if !allowed {
		return deny(ack, common.ErrAgentNotRegistered)
	}

	ack.OpenTime = res.OpenTime
	if helper.AuthWithNhpCallbackFunc == nil {
		return ack, fmt.Errorf("AuthWithNHP: callback is null")
	}
	return helper.AuthWithNhpCallbackFunc(req, res)
}

func postAuthorize(pubkey string) (bool, error) {
	body, err := json.Marshal(map[string]string{"pubkey": pubkey})
	if err != nil {
		return false, err
	}
	resp, err := http.Post(authURL, "application/json", bytes.NewReader(body))
	if err != nil {
		return false, err
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, resp.Body)
	switch resp.StatusCode {
	case http.StatusOK:
		return true, nil
	case http.StatusForbidden:
		return false, nil
	default:
		return false, fmt.Errorf("auth status %d", resp.StatusCode)
	}
}

func deny(ack *common.ServerKnockAckMsg, cause *common.Error) (*common.ServerKnockAckMsg, error) {
	ack.ErrCode = cause.ErrorCode()
	ack.ErrMsg = cause.Error()
	return ack, cause
}
