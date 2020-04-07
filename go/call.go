package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"time"

	"nhooyr.io/websocket"
	"nhooyr.io/websocket/wsjson"
)

type requestLogin struct {
	Login    string `json:"login"`
	Password string `json:"password"`
}

type responseLogin struct {
	Data struct {
		AccessToken string `json:"accessToken"`
	} `json:"data"`
}

type responseAPIKeys struct {
	Data []string `json:"data"`
}

type responseAPIKey struct {
	Data struct {
		APIKey string `json:"apiKey"`
	} `json:"data"`
}

type rpcRequest struct {
	ID      int               `json:"id"`
	Jsonrpc string            `json:"jsonrpc"`
	Method  string            `json:"method"`
	Params  map[string]string `json:"params"`
}

type rpcResponse struct {
	ID      int                    `json:"id"`
	Jsonrpc string                 `json:"jsonrpc"`
	Method  string                 `json:"method"`
	Params  map[string]interface{} `json:"params"`
	Result  struct {
		Message string `json:"message"`
	} `json:"result"`
}

func main() {
	args := os.Args[1:]
	if len(args) != 3 {
		log.Fatal("Wrong arguments")
	}
	RequestLogin, err := json.Marshal(&requestLogin{
		Login:    args[0],
		Password: args[1],
	})
	if err != nil {
		log.Fatalf("Login JSON marshall error: %s", err)
	}
	client := &http.Client{}
	resp, err := client.Post("https://testapi.megafon.ru/api/rest/login", "application/json", bytes.NewBuffer(RequestLogin))
	if err != nil {
		log.Fatalf("Login POST error: %s", err)
	}
	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		log.Fatalf("Login Read error: %s", err)
	}
	var ResponseLogin responseLogin
	err = json.Unmarshal([]byte(body), &ResponseLogin)
	if err != nil {
		log.Fatalf("Login JSON Unmarshal error: %s", err)
	}
	req, err := http.NewRequest("GET", "https://testapi.megafon.ru/api/rest/apiKeys", bytes.NewBuffer(nil))
	if err != nil {
		log.Fatalf("apiKeys create GET request error: %s", err)
	}
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", ResponseLogin.Data.AccessToken))
	req.Header.Add("Accept", "application/json")
	resp, err = client.Do(req)
	if err != nil {
		log.Fatalf("apiKeys execute GET request error: %s", err)
	}
	body, err = ioutil.ReadAll(resp.Body)
	if err != nil {
		log.Fatalf("apiKeys read GET request error: %s", err)
	}
	var ResponseAPIKeys responseAPIKeys
	err = json.Unmarshal([]byte(body), &ResponseAPIKeys)
	if err != nil {
		log.Fatalf("apiKeys unmarshall GET request error: %s", err)
	}
	var apiKey string
	if len(ResponseAPIKeys.Data) == 0 {
		req, err := http.NewRequest("POST", "https://testapi.megafon.ru/api/rest/apiKeys", bytes.NewBuffer(nil))
		if err != nil {
			log.Fatalf("apiKeys create POST request error: %s", err)
		}
		req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", ResponseLogin.Data.AccessToken))
		req.Header.Add("Accept", "application/json")
		resp, err = client.Do(req)
		if err != nil {
			log.Fatalf("apiKeys execute POST request error: %s", err)
		}
		body, err = ioutil.ReadAll(resp.Body)
		if err != nil {
			log.Fatalf("apiKeys read POST request error: %s", err)
		}
		var ResponseAPIKey responseAPIKey
		err = json.Unmarshal([]byte(body), &ResponseAPIKey)
		if err != nil {
			log.Fatalf("apiKeys unmarshall POST request error: %s", err)
		}
		apiKey = ResponseAPIKey.Data.APIKey
	} else {
		apiKey = ResponseAPIKeys.Data[0]
	}
	log.Println(apiKey)
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	c, _, err := websocket.Dial(ctx, fmt.Sprintf("wss://testapi.megafon.ru/v1/api/%s", apiKey), nil)
	if err != nil {
		log.Fatalf("WebSocket dial error: %s", err)
	}
	defer c.Close(websocket.StatusInternalError, "WebSocket internal error")
	id := 0
	finished := make(chan bool)
	go func(finished chan bool) {
		for {
			var RPCResponse rpcResponse
			err = wsjson.Read(ctx, c, &RPCResponse)
			if err != nil {
				if websocket.CloseStatus(err) == websocket.StatusNormalClosure {
					finished <- true
				} else {
					log.Fatalf("WebSocket read error: %s", err)
				}
			} else {
				log.Println(RPCResponse)
			}
			session := fmt.Sprintf("%v", RPCResponse.Params["call_session"])
			switch RPCResponse.Method {
			case "onCallAnswer":
				id++
				err = wsjson.Write(ctx, c, &rpcRequest{
					ID:      id,
					Jsonrpc: "2.0",
					Method:  "callFilePlay",
					Params:  map[string]string{"call_session": session, "filename": "welcome.pcm"},
				})
				if err != nil {
					log.Fatal(err)
				}
			case "onCallFilePlay":
				id++
				err = wsjson.Write(ctx, c, &rpcRequest{
					ID:      id,
					Jsonrpc: "2.0",
					Method:  "callTerminate",
					Params:  map[string]string{"call_session": session},
				})
				if err != nil {
					log.Fatal(err)
				}
			case "onCallTerminate":
				finished <- true
			}
		}
	}(finished)
	err = wsjson.Write(ctx, c, &rpcRequest{
		ID:      id,
		Jsonrpc: "2.0",
		Method:  "callMake",
		Params:  map[string]string{"bnum": args[2]},
	})
	if err != nil {
		log.Fatal(err)
	}
	<-finished
	c.Close(websocket.StatusNormalClosure, "")
	req, err = http.NewRequest("DELETE", fmt.Sprintf("https://testapi.megafon.ru/api/rest/apiKeys/%s", apiKey), bytes.NewBuffer(nil))
	if err != nil {
		log.Fatalf("apiKeys create DELETE request error: %s", err)
	}
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", ResponseLogin.Data.AccessToken))
	req.Header.Add("Accept", "application/json")
	resp, err = client.Do(req)
	if err != nil {
		log.Fatalf("apiKeys execute DELETE request error: %s", err)
	}
}
