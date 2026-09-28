// Copy into cloudflared 2026.9.3/ingress/middleware and run:
// go test ./ingress/middleware -run TestKnightSatJWT -v
// Uses the real constructor/validator, but ephemeral fixture keys, not live tokens.
package middleware

import (
	"context"
	"crypto/rand"
	"crypto/rsa"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/go-jose/go-jose/v4"
	"github.com/go-jose/go-jose/v4/jwt"
)

type fixtureTransport func(*http.Request) (*http.Response, error)

func (f fixtureTransport) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

func TestKnightSatJWT(t *testing.T) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	wrongKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	const issuer = "https://ksat24-fixture.cloudflareaccess.com"
	keys, err := json.Marshal(jose.JSONWebKeySet{Keys: []jose.JSONWebKey{{Key: &key.PublicKey, KeyID: "fixture", Algorithm: "RS256", Use: "sig"}}})
	if err != nil {
		t.Fatal(err)
	}
	old := http.DefaultTransport
	http.DefaultTransport = fixtureTransport(func(r *http.Request) (*http.Response, error) {
		if r.URL.String() != issuer+"/cdn-cgi/access/certs" {
			t.Fatalf("unexpected key URL: %s", r.URL)
		}
		return &http.Response{StatusCode: 200, Header: http.Header{"Content-Type": {"application/json"}}, Body: io.NopCloser(strings.NewReader(string(keys)))}, nil
	})
	t.Cleanup(func() { http.DefaultTransport = old })
	for _, name := range []string{"valid", "missing", "malformed", "issuer", "audience", "signature", "expiry"} {
		t.Run(name, func(t *testing.T) {
			claims := jwt.Claims{Issuer: issuer, Audience: jwt.Audience{"knightsat-fixture"}, Expiry: jwt.NewNumericDate(time.Now().Add(time.Hour))}
			signingKey := key
			switch name {
			case "issuer":
				claims.Issuer = "https://wrong-team.cloudflareaccess.com"
			case "audience":
				claims.Audience = jwt.Audience{"another-application"}
			case "signature":
				signingKey = wrongKey
			case "expiry":
				claims.Expiry = jwt.NewNumericDate(time.Now().Add(-time.Hour))
			}
			signer, err := jose.NewSigner(jose.SigningKey{Algorithm: jose.RS256, Key: jose.JSONWebKey{Key: signingKey, KeyID: "fixture"}}, nil)
			if err != nil {
				t.Fatal(err)
			}
			token, err := jwt.Signed(signer).Claims(claims).Serialize()
			if err != nil {
				t.Fatal(err)
			}
			if name == "malformed" {
				token = "invalid"
			}
			if name == "missing" {
				token = ""
			}
			req := httptest.NewRequest("GET", "http://origin/health", nil)
			req.Header.Set("Cf-Access-Jwt-Assertion", token)
			validator := NewJWTValidator("ksat24-fixture", "", []string{"knightsat-fixture"})
			result, err := validator.Handle(context.Background(), req)
			accepted := err == nil && result != nil && !result.ShouldFilterRequest
			if accepted != (name == "valid") {
				t.Fatalf("accepted=%v; error=%v", accepted, err)
			}
		})
	}
}
