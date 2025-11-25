{ pkgs }:

pkgs.python3Packages.buildPythonApplication {
  pname = "headscale-mullvad";
  version = "0.1.0";
  format = "pyproject";

  src = pkgs.lib.cleanSource ./.;

  nativeBuildInputs = with pkgs.python3Packages; [
    setuptools
    wheel
  ];

  propagatedBuildInputs = with pkgs.python3Packages; [
    rich
    python-dotenv
    typer
    requests
    shellingham
    colorama
  ];
}