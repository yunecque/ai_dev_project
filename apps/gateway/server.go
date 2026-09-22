package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"

	domainv1 "github.com/yunecque/ai_dev_project/apps/gen/domain/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const (
	maxTitleLen       = 200
	maxDescriptionLen = 4000
	maxBodyBytes      = 64 * 1024
	maxListLimit      = 200
)

// domainService is satisfied by the generated gRPC DomainService client.
type domainService interface {
	CreateRequest(ctx context.Context, in *domainv1.CreateRequestRequest, opts ...grpc.CallOption) (*domainv1.CreateRequestResponse, error)
	UpdateRequestStatus(ctx context.Context, in *domainv1.UpdateRequestStatusRequest, opts ...grpc.CallOption) (*domainv1.UpdateRequestStatusResponse, error)
	GetRequest(ctx context.Context, in *domainv1.GetRequestRequest, opts ...grpc.CallOption) (*domainv1.GetRequestResponse, error)
	ListRequests(ctx context.Context, in *domainv1.ListRequestsRequest, opts ...grpc.CallOption) (*domainv1.ListRequestsResponse, error)
}

type apiServer struct {
	verifier tokenVerifier
	domain   domainService
}

func newAPIServer(verifier tokenVerifier, domain domainService) *apiServer {
	return &apiServer{verifier: verifier, domain: domain}
}

func (s *apiServer) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.handleHealth)
	mux.HandleFunc("GET /requests", s.handleListRequests)
	mux.HandleFunc("POST /requests", s.handleCreateRequest)
	mux.HandleFunc("GET /requests/{id}", s.handleGetRequest)
	mux.HandleFunc("PATCH /requests/{id}/status", s.handleUpdateStatus)
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

type requestListResponse struct {
	Requests []requestResponse `json:"requests"`
}

type updateStatusPayload struct {
	Status string `json:"status"`
}

func toRequestResponse(request *domainv1.Request) requestResponse {
	return requestResponse{
		ID:        request.GetId(),
		Title:     request.GetTitle(),
		Status:    request.GetStatus(),
		CreatedAt: request.GetCreatedAt(),
	}
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
	writeJSON(w, http.StatusCreated, toRequestResponse(created))
}

func (s *apiServer) handleListRequests(w http.ResponseWriter, r *http.Request) {
	if _, err := s.bearerSubject(r); err != nil {
		writeError(w, http.StatusUnauthorized, "unauthenticated", err.Error())
		return
	}

	query := r.URL.Query()
	var limit int
	if raw := strings.TrimSpace(query.Get("limit")); raw != "" {
		parsed, err := strconv.Atoi(raw)
		if err != nil || parsed < 1 || parsed > maxListLimit {
			writeError(w, http.StatusBadRequest, "invalid_input", "limit must be between 1 and 200")
			return
		}
		limit = parsed
	}

	response, err := s.domain.ListRequests(r.Context(), &domainv1.ListRequestsRequest{
		Status:  strings.TrimSpace(query.Get("status")),
		Subject: strings.TrimSpace(query.Get("subject")),
		Limit:   int32(limit),
	})
	if err != nil {
		writeDomainError(w, err)
		return
	}

	requests := make([]requestResponse, 0, len(response.GetRequests()))
	for _, request := range response.GetRequests() {
		requests = append(requests, toRequestResponse(request))
	}
	writeJSON(w, http.StatusOK, requestListResponse{Requests: requests})
}

func (s *apiServer) handleGetRequest(w http.ResponseWriter, r *http.Request) {
	if _, err := s.bearerSubject(r); err != nil {
		writeError(w, http.StatusUnauthorized, "unauthenticated", err.Error())
		return
	}

	response, err := s.domain.GetRequest(r.Context(), &domainv1.GetRequestRequest{
		RequestId: r.PathValue("id"),
	})
	if err != nil {
		writeDomainError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, toRequestResponse(response.GetRequest()))
}

func (s *apiServer) handleUpdateStatus(w http.ResponseWriter, r *http.Request) {
	subject, err := s.bearerSubject(r)
	if err != nil {
		writeError(w, http.StatusUnauthorized, "unauthenticated", err.Error())
		return
	}

	var payload updateStatusPayload
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, maxBodyBytes))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&payload); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_input", "malformed or oversized JSON body")
		return
	}
	if strings.TrimSpace(payload.Status) == "" {
		writeError(w, http.StatusBadRequest, "invalid_input", "status is required")
		return
	}

	response, err := s.domain.UpdateRequestStatus(r.Context(), &domainv1.UpdateRequestStatusRequest{
		RequestId:    r.PathValue("id"),
		NewStatus:    strings.TrimSpace(payload.Status),
		ActorSubject: subject,
	})
	if err != nil {
		writeDomainError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, toRequestResponse(response.GetRequest()))
}

// writeDomainError maps gRPC status codes to HTTP responses (fail-closed on anything else).
func writeDomainError(w http.ResponseWriter, err error) {
	switch status.Code(err) {
	case codes.NotFound:
		writeError(w, http.StatusNotFound, "not_found", "request not found")
	case codes.InvalidArgument:
		writeError(w, http.StatusBadRequest, "invalid_input", err.Error())
	case codes.FailedPrecondition:
		writeError(w, http.StatusConflict, "illegal_transition", err.Error())
	default:
		writeError(w, http.StatusBadGateway, "domain_unavailable", err.Error())
	}
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
