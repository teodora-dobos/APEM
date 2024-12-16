def node_zone_mapper(zonal_configuration: str, lat: float, lon: float) -> int:
    """
    Map a node to a specific zone based on its latitude and longitude coordinates.
    """
    if zonal_configuration == 'zonal_DE2-k':
        if (lat < 52 and lon < 7.25) or (lat < 51.4 and lon < 8) or (lat < 51.1 and lon < 10) or (lat < 50.3):
            return 1  # south
        else:
            return 2  # north
    elif zonal_configuration == 'zonal_DE2-s':
        if (lat < 52.9 and lon < 8.5) or (lat < 51.75 and lon < 10.25) or (lat < 50.3):
            return 1  # south
        else:
            return 2  # north
    elif zonal_configuration == 'zonal_DE3':
        if (lat < 51.2 and lon < 8) or (lat < 51 and lon < 10.2) or (lat < 50.3):
            return 1  # south
        elif (lat > 52.2 and lon < 11) or (lat > 51.5 and lon < 10.3) or (lon < 10):
            return 2  # north-west
        else:
            return 3  # north-east
    elif zonal_configuration == 'zonal_DE4':
        if (lat > 53 and lon < 7.1) or (52.2 < lat < 54 and lon < 9) or (51.7 < lat < 53.3 and 10.75 > lon > 7.4) \
                or (52 > lat > 50.85 and 8 < lon < 10):
            return 1  # north-west
        elif (lon < 8.28) or (49.5 < lat < 50.2 and lon < 9.1):
            return 2  # west
        elif (lat > 50.35) or (lat > 50.2 and lon > 10):
            return 3  # east
        else:
            return 4  # south


