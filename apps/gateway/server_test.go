package main

import (
	"context"
	"encoding/json"
	"errors"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	domainv1 "github.com/yunecque/ai_dev_project/apps/gen/domain/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	"google.golang.org/grpc/test/bufconn"
)

type fakeVerifier struct {
	subject string
	err     error
}

func (f fakeVerifier) Verify(context.Context, string) (string, error) {
	return f.subject, f.err
}

type fakeDomain struct {
	domainv1.UnimplementedDomainServiceServer
	err        error
	gotSubject string
}

func (f *fakeDomain) CreateRequest(_ context.Context, in *domainv1.CreateRequestRequest) (*domainv1.CreateRequestResponse, error) {
	f.gotSubject = in.GetSubject()
	if f.err != nil {
		return nil, f.err
	}
	return &domainv1.CreateRequestResponse{
		Request: &domainv1.Request{
			Id:        "r-1",
			Title:     in.GetTitle(),
			Status:    "created",
			CreatedAt: "2026-09-22T00:00:00Z",
		},
	}, nil
}

func startDomain(t *testing.T, impl domainv1.DomainServiceServer) domainv1.DomainServiceClient {
	t.Helper()
	listener := bufconn.Listen(1024 * 1024)
	server := grpc.NewServer()
	domainv1.RegisterDomainServiceServer(server, impl)
	go func() {
		if err := server.Serve(listener); err != nil {
			t.Logf("domain serve: %v", err)
		}
	}()
	t.Cleanup(server.Stop)

	conn, err := grpc.NewClient(
		"passthrough:///bufnet",
		grpc.WithContextDialer(func(ctx context.Context, _ string) (net.Conn, error) {
			return listener.DialContext(ctx)
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatalf("dial domain: %v", err)
	}
	t.Cleanup(func() { _ = conn.Close() })
	return domainv1.NewDomainServiceClient(conn)
}

func newTestServer(t *testing.T, verifier tokenVerifier, domain domainv1.DomainServiceServer) (*httptest.Server, *fakeDomain) {
	t.Helper()
	fake, _ := domain.(*fakeDomain)
	client := startDomain(t, domain)
	api := newAPIServer(verifier, client)
	ts := httptest.NewServer(api.routes())
	t.Cleanup(ts.Close)
	return ts, fake
}

func postCreate(t *testing.T, ts *httptest.Server, token, body string) *http.Response {
	t.Helper()
	request, err := http.NewRequest(http.MethodPost, ts.URL+"/requests", strings.NewReader(body))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	if token != "" {
		request.Header.Set("Authorization", "Bearer "+token)
	}
	request.Header.Set("Content-Type", "application/json")
	response, err := ts.Client().Do(request)
	if err != nil {
		t.Fatalf("do request: %v", err)
	}
	t.Cleanup(func() { _ = response.Body.Close() })
	return response
}

func TestHealthz(t *testing.T) {
	ts, _ := newTestServer(t, fakeVerifier{subject: "user-1"}, &fakeDomain{})
	response, err := ts.Client().Get(ts.URL + "/healthz")
	if err != nil {
		t.Fatalf("get healthz: %v", err)
	}
	defer func() { _ = response.Body.Close() }()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.StatusCode)
	}
}

func TestCreateRequestSucceeds(t *testing.T) {
	ts, domain := newTestServer(t, fakeVerifier{subject: "user-123"}, &fakeDomain{})
	response := postCreate(t, ts, "good-token", `{"title":"Reset VPN","description":"please"}`)
	if response.StatusCode != http.StatusCreated {
		t.Fatalf("status = %d, want 201", response.StatusCode)
	}
	var body requestResponse
	if err := json.NewDecoder(response.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if body.ID != "r-1" || body.Status != "created" {
		t.Fatalf("unexpected body: %+v", body)
	}
	if domain.gotSubject != "user-123" {
		t.Fatalf("subject forwarded = %q, want user-123", domain.gotSubject)
	}
}

func TestMissingAuthorizationIsUnauthorized(t *testing.T) {
	ts, _ := newTestServer(t, fakeVerifier{subject: "user-1"}, &fakeDomain{})
	response := postCreate(t, ts, "", `{"title":"x"}`)
	if response.StatusCode != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", response.StatusCode)
	}
}

func TestInvalidTokenIsUnauthorized(t *testing.T) {
	ts, _ := newTestServer(t, fakeVerifier{err: errors.New("token expired")}, &fakeDomain{})
	response := postCreate(t, ts, "bad", `{"title":"x"}`)
	if response.StatusCode != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", response.StatusCode)
	}
}

func TestEmptyTitleIsRejected(t *testing.T) {
	ts, _ := newTestServer(t, fakeVerifier{subject: "user-1"}, &fakeDomain{})
	response := postCreate(t, ts, "good", `{"title":"   "}`)
	if response.StatusCode != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", response.StatusCode)
	}
}

func TestTitleTooLongIsRejected(t *testing.T) {
	ts, _ := newTestServer(t, fakeVerifier{subject: "user-1"}, &fakeDomain{})
	body, _ := json.Marshal(map[string]string{"title": strings.Repeat("a", maxTitleLen+1)})
	response := postCreate(t, ts, "good", string(body))
	if response.StatusCode != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", response.StatusCode)
	}
}

func TestUnknownFieldIsRejected(t *testing.T) {
	ts, _ := newTestServer(t, fakeVerifier{subject: "user-1"}, &fakeDomain{})
	response := postCreate(t, ts, "good", `{"title":"x","unexpected":true}`)
	if response.StatusCode != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", response.StatusCode)
	}
}

func TestDomainFailureIsBadGateway(t *testing.T) {
	domain := &fakeDomain{err: status.Error(codes.Internal, "boom")}
	ts, _ := newTestServer(t, fakeVerifier{subject: "user-1"}, domain)
	response := postCreate(t, ts, "good", `{"title":"x"}`)
	if response.StatusCode != http.StatusBadGateway {
		t.Fatalf("status = %d, want 502", response.StatusCode)
	}
}

func TestNewOIDCVerifierRequiresIssuer(t *testing.T) {
	if _, err := newOIDCVerifier(context.Background(), "", "client"); err == nil {
		t.Fatal("expected error for empty issuer")
	}
}
