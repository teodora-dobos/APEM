The ``create_pypsa_csv.py`` file can be used to compute the csv files in ``raw_data/pypsa_eur_{name}`` from the PyPSA network (``.nc``) files in the same directories.
They also compute some statistics and draw some plots which can be found in the ``pypsa_eur_{name}/stats`` and ``pypsa_eur_{name}/plots`` directories.

Note: The config.yaml file provided in this directory can be used with PyPSA-Eur to generate custom PyPSA network files.
If PyPSA-Eur is properly installed (see: https://pypsa-eur.readthedocs.io/en/latest/installation.html), then the config file can be stored in the ``pypsa-eur/config`` directory. If the corresponding ``mamba``or ``conda`` environment is created and activated with

``mamba env create -f envs/environment.yaml``

``mamba activate pypsa-eur``

or 

``conda env create -f envs/environment.yaml``

``conda activate pypsa-eur``

the network files can be generated using

``snakemake -call solve_elec_networks``

and can be found in the ``pypsa-eur/results/networks`` directory.









