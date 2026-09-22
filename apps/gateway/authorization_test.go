package main

import (
	"context"
	"errors"
	"net/http"
	"testing"
)

type mapVerifier struct {
	byToken map[string]string
}

func (m mapVerifier) Verify(_ context.Context, rawToken string) (string, error) {
	if subject, ok := m.byToken[rawToken]; ok {
		return subject, nil
	}
	return "", errors.New("unknown token")
}

func TestAuthorizationRejectsNonBearerScheme(t *testing.T) {
	ts, _ := newTestServer(t, mapVerifier{byToken: map[string]string{"t": "user-1"}}, &fakeDomain{})
	request, _ := http.NewRequest(http.MethodPost, ts.URL+"/requests", nil)
	request.Header.Set("Authorization", "Basic dXNlcjpwYXNz")
	response, err := ts.Client().Do(request)
	if err != nil {
		t.Fatalf("do: %v", err)
	}
	defer func() { _ = response.Body.Close() }()
	if response.StatusCode != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", response.StatusCode)
	}
}

func TestAuthorizationRejectsEmptyBearer(t *testing.T) {
	ts, _ := newTestServer(t, mapVerifier{byToken: map[string]string{"t": "user-1"}}, &fakeDomain{})
	response := postCreate(t, ts, "", `{"title":"x"}`)
	if response.StatusCode != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", response.StatusCode)
	}
}

func TestBodyCannotOverrideAuthenticatedSubject(t *testing.T) {
	ts, domain := newTestServer(t, mapVerifier{byToken: map[string]string{"t": "user-1"}}, &fakeDomain{})
	response := postCreate(t, ts, "t", `{"title":"x","subject":"admin"}`)
	if response.StatusCode != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 (unknown field)", response.StatusCode)
	}
	if domain.gotSubject != "" {
		t.Fatalf("domain must not be called on rejected input, got subject %q", domain.gotSubject)
	}
}

func TestDistinctTokensYieldDistinctSubjects(t *testing.T) {
	verifier := mapVerifier{byToken: map[string]string{"alice-token": "alice", "bob-token": "bob"}}
	ts, domain := newTestServer(t, verifier, &fakeDomain{})

	if response := postCreate(t, ts, "alice-token", `{"title":"a"}`); response.StatusCode != http.StatusCreated {
		t.Fatalf("alice status = %d", response.StatusCode)
	}
	if domain.gotSubject != "alice" {
		t.Fatalf("subject = %q, want alice", domain.gotSubject)
	}

	if response := postCreate(t, ts, "bob-token", `{"title":"b"}`); response.StatusCode != http.StatusCreated {
		t.Fatalf("bob status = %d", response.StatusCode)
	}
	if domain.gotSubject != "bob" {
		t.Fatalf("subject = %q, want bob", domain.gotSubject)
	}
}

func TestUnknownTokenIsUnauthorized(t *testing.T) {
	ts, _ := newTestServer(t, mapVerifier{byToken: map[string]string{"t": "user-1"}}, &fakeDomain{})
	response := postCreate(t, ts, "nope", `{"title":"x"}`)
	if response.StatusCode != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", response.StatusCode)
	}
}
