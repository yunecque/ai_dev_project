package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"time"

	domainv1 "github.com/yunecque/ai_dev_project/apps/gen/domain/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	issuer := os.Getenv("OIDC_ISSUER")
	clientID := os.Getenv("OIDC_CLIENT_ID")
	domainAddr := getenv("DOMAIN_ADDR", "localhost:9090")
	listenAddr := getenv("GATEWAY_LISTEN", ":8081")

	verifier, err := newOIDCVerifier(ctx, issuer, clientID)
	if err != nil {
		log.Fatalf("gateway: oidc verifier: %v", err)
	}

	conn, err := grpc.NewClient(domainAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatalf("gateway: domain client: %v", err)
	}
	defer func() { _ = conn.Close() }()

	server := newAPIServer(verifier, domainv1.NewDomainServiceClient(conn))
	log.Printf("gateway: listening on %s (domain=%s)", listenAddr, domainAddr)
	if err := http.ListenAndServe(listenAddr, server.routes()); err != nil {
		log.Fatalf("gateway: %v", err)
	}
}

func getenv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
