package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strings"

	domainv1 "github.com/yunecque/ai_dev_project/apps/gen/domain/v1"
	"google.golang.org/grpc"
)

const (
	maxTitleLen       = 200
	maxDescriptionLen = 4000
	maxBodyBytes      = 64 * 1024
)

// requestCreator is satisfied by the generated gRPC DomainService client.
type requestCreator interface {
	CreateRequest(ctx context.Context, in *domainv1.CreateRequestRequest, opts ...grpc.CallOption) (*domainv1.CreateRequestResponse, error)
}

type apiServer struct {
	verifier tokenVerifier
	domain   requestCreator
}

func newAPIServer(verifier tokenVerifier, domain requestCreator) *apiServer {
	return &apiServer{verifier: verifier, domain: domain}
}

func (s *apiServer) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.handleHealth)
	mux.HandleFunc("POST /requests", s.handleCreateRequest)
	return mux
}

func (s *apiServer) handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

type createRequestPayload struct {
	Title       string `json:"title"`
	Description string `json:"description"`
}

type requestResponse struct {
	ID        string `json:"id"`
	Title     string `json:"title"`
	Status    string `json:"status"`
	CreatedAt string `json:"created_at"`
}

func (s *apiServer) handleCreateRequest(w http.ResponseWriter, r *http.Request) {
	subject, err := s.bearerSubject(r)
	if err != nil {
		writeError(w, http.StatusUnauthorized, "unauthenticated", err.Error())
		return
	}

	var payload createRequestPayload
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, maxBodyBytes))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&payload); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_input", "malformed or oversized JSON body")
		return
	}
	if problem := validatePayload(payload); problem != "" {
		writeError(w, http.StatusBadRequest, "invalid_input", problem)
		return
	}

	response, err := s.domain.CreateRequest(r.Context(), &domainv1.CreateRequestRequest{
		Title:       payload.Title,
		Description: payload.Description,
		Subject:     subject,
	})
	if err != nil {
		writeError(w, http.StatusBadGateway, "domain_unavailable", err.Error())
		return
	}
	created := response.GetRequest()
	writeJSON(w, http.StatusCreated, requestResponse{
		ID:        created.GetId(),
		Title:     created.GetTitle(),
		Status:    created.GetStatus(),
		CreatedAt: created.GetCreatedAt(),
	})
}

func (s *apiServer) bearerSubject(r *http.Request) (string, error) {
	header := r.Header.Get("Authorization")
	const prefix = "Bearer "
	if !strings.HasPrefix(header, prefix) {
		return "", errors.New("missing bearer token")
	}
	raw := strings.TrimSpace(strings.TrimPrefix(header, prefix))
	if raw == "" {
		return "", errors.New("missing bearer token")
	}
	return s.verifier.Verify(r.Context(), raw)
}

func validatePayload(payload createRequestPayload) string {
	title := strings.TrimSpace(payload.Title)
	if title == "" {
		return "title is required"
	}
	if len([]rune(payload.Title)) > maxTitleLen {
		return "title exceeds maximum length"
	}
	if len([]rune(payload.Description)) > maxDescriptionLen {
		return "description exceeds maximum length"
	}
	return ""
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

type errorBody struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func writeError(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, errorBody{Code: code, Message: message})
}
