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

      package = pkgs.callPackage ./package.nix { };
    in
    {
      packages.${system} = {
        default = package;
        headscale-mullvad = package;
      };

      apps.${system}.default = {
        type = "app";
        program = "${self.packages.${system}.default}/bin/headscale-mullvad";
      };
    };
}
