{
  description = "LangLab development environment — includes E2E test tooling";

  inputs = {
    nixpkgs.url     = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        # Python env for running the server + all tests (unit and E2E)
        pythonEnv = pkgs.python313.withPackages (ps: with ps; [
          playwright   # Python bindings — version matched to playwright-driver below
          pytest       # E2E test runner
        ]);

      in {
        devShells.default = pkgs.mkShell {
          packages = [
            pythonEnv
            pkgs.playwright-driver.browsers  # Chromium (and friends) from Nix store
            pkgs.ffmpeg                      # Audio clip extraction in server + CLI
          ];

          shellHook = ''
            # Point playwright to Nix-managed browsers (avoids downloading anything)
            export PLAYWRIGHT_BROWSERS_PATH=${pkgs.playwright-driver.browsers}
            export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true

            echo ""
            echo "LangLab dev shell ready."
            echo "  Start server : python server.py"
            echo "  Unit tests   : python -m unittest discover -s tests -p 'test_*.py'"
            echo "  E2E tests    : pytest tests/e2e/  (server must be on :8080)"
            echo "  All tests    : pytest tests/"
            echo ""
          '';
        };
      });
}
