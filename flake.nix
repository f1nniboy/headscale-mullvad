{
  description = "Automatically create Wireguard exit nodes in your Headscale tailnet";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
    in
    {
      packages.${system}.default = pkgs.callPackage ./package.nix { };

      apps.${system}.default = {
        type = "app";
        program = "${self.packages.${system}.default}/bin/headscale-mullvad";
      };
    };
}
