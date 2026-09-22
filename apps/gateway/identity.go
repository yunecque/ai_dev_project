package main

import (
	"context"
	"errors"

	"github.com/coreos/go-oidc/v3/oidc"
)

// tokenVerifier verifies a raw bearer token and returns the authenticated subject.
type tokenVerifier interface {
	Verify(ctx context.Context, rawToken string) (string, error)
}

// oidcVerifier validates tokens against an OIDC provider (Keycloak, ADR-0009).
type oidcVerifier struct {
	verifier *oidc.IDTokenVerifier
}

func newOIDCVerifier(ctx context.Context, issuer, clientID string) (tokenVerifier, error) {
	if issuer == "" {
		return nil, errors.New("oidc issuer must not be empty")
	}
	provider, err := oidc.NewProvider(ctx, issuer)
	if err != nil {
		return nil, err
	}
	return &oidcVerifier{verifier: provider.Verifier(&oidc.Config{ClientID: clientID})}, nil
}

func (v *oidcVerifier) Verify(ctx context.Context, rawToken string) (string, error) {
	token, err := v.verifier.Verify(ctx, rawToken)
	if err != nil {
		return "", err
	}
	return token.Subject, nil
}
