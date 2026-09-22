package main

import (
	"context"
	"errors"

	"github.com/coreos/go-oidc/v3/oidc"
)

// identity is the verified caller context derived from a bearer token.
type identity struct {
	Subject string
	Roles   []string
}

// tokenVerifier verifies a raw bearer token and returns the authenticated identity.
type tokenVerifier interface {
	Verify(ctx context.Context, rawToken string) (identity, error)
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

func (v *oidcVerifier) Verify(ctx context.Context, rawToken string) (identity, error) {
	token, err := v.verifier.Verify(ctx, rawToken)
	if err != nil {
		return identity{}, err
	}
	var claims struct {
		RealmAccess struct {
			Roles []string `json:"roles"`
		} `json:"realm_access"`
	}
	// Claims parsing is best-effort: a token without roles is a plain user.
	_ = token.Claims(&claims)
	return identity{Subject: token.Subject, Roles: claims.RealmAccess.Roles}, nil
}
