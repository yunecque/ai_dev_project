package main

import (
	"context"
	"log"
	"net"
	"os"

	"github.com/yunecque/ai_dev_project/apps/domain/internal/domain"
	domainv1 "github.com/yunecque/ai_dev_project/apps/gen/domain/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"
)

func main() {
	ctx := context.Background()
	dsn := getenv("DATABASE_URL", "postgres://sdlc:sdlc-dev-password@localhost:5432/requests")
	listenAddr := getenv("DOMAIN_LISTEN", ":9090")

	store, err := domain.NewPostgresStore(ctx, dsn)
	if err != nil {
		log.Fatalf("domain: postgres: %v", err)
	}
	defer store.Close()

	listener, err := net.Listen("tcp", listenAddr)
	if err != nil {
		log.Fatalf("domain: listen: %v", err)
	}

	server := grpc.NewServer()
	domainv1.RegisterDomainServiceServer(server, domain.NewService(store))
	reflection.Register(server)

	log.Printf("domain: listening on %s", listenAddr)
	if err := server.Serve(listener); err != nil {
		log.Fatalf("domain: serve: %v", err)
	}
}

func getenv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
