def node_zone_mapper(zonal_configuration: str, lat: float, lon: float) -> int:
    """
    Map a node to a specific zone based on its latitude and longitude coordinates.
    Note: The configurations 'zonal_DE2-k', 'zonal_DE2-s', 'zonal_DE3', 'zonal_DE4' / 'zonal_DE4-refined' were suggested by ACER for the BZR.
    """
    if zonal_configuration == 'zonal_DE2-k': # DE2 (k-means)
        if (lat < 52 and lon < 7.25) or (lat < 51.4 and lon < 8) or (lat < 51.1 and lon < 10) or (lat < 50.3):
            return 2  # SOUTH
        else:
            return 1  # NORTH
        
    elif zonal_configuration == 'zonal_DE2-s': # DE2 (spectral)
        if (lat < 52.9 and lon < 8.5) or (lat < 51.75 and lon < 10.25) or (lat < 50.3):
            return 2  # SOUTH
        else:
            return 1  # NORTH
        
    elif zonal_configuration == 'zonal_DE3': # DE3 (spectral)
        if (lat < 51.2 and lon < 8) or (lat < 51 and lon < 10.2) or (lat < 50.3):
            return 3  # SOUTH
        elif (lat > 52.2 and lon < 11) or (lat > 51.5 and lon < 10.3) or (lon < 10):
            return 1  # NORTH-WEST
        else:
            return 2  # NORTH-EAST
        
    elif zonal_configuration == 'zonal_DE4': # DE4 (spectral)
        if (lat > 53 and lon < 7.1) or (52.2 < lat < 54 and lon < 9) or (51.7 < lat < 53.3 and 7.4 < lon < 10.75) \
                or (50.85 < lat < 52 and 8 < lon < 10):
            return 1  # NORTH-WEST
        elif (lon < 8.28) or (49.5 < lat < 50.2 and lon < 9.1):
            return 2  # WEST
        elif (lat > 50.35) or (lat > 50.2 and lon > 10):
            return 3  # EAST
        else:
            return 4  # SOUTH
        
    elif zonal_configuration == 'zonal_DE4-refined': # DE4 (spectral, refined)
        if ((47.20 <= lat <= 50.63 and 9.52 <= lon <= 12.97) # Bavaria
                or (47.55 <= lat <= 49.78 and 7.68 <= lon <= 9.66)
                or (lat <= 48.9)):
            zone = 4  # SOUTH
        elif ((50.56 <= lat <= 51.65 and 9.87 <= lon <= 11.04) # Thuringia
                or (50.79 <= lat <= 51.68 and 12.08 <= lon <= 14.60) # Saxony
                or (51.35 <= lat <= 53.55 and 11.41 <= lon <= 16) # Brandenburg
                or (51.38 <= lat <= 52.88 and 10.88 <= lon <= 12.37) # Saxony-Anhalt
                or (52.33 <= lat <= 52.67 and 13.08 <= lon <= 13.76) # Berlin
                or (53.21 <= lat <= 54.68 and 11.00 <= lon <= 14.24) # Mecklenburg-Vorpommern
                or (53.37 <= lat <= 53.72 and 9.76 <= lon <= 10.23) # Hamburg
                or (54.41 <= lat <= 55.05 and 8.08 <= lon <= 10.12) # Schleswig-Holstein
                # adjustments
                or (lon >= 14.5) 
                or (lat >= 50.5 and lon >= 11) 
                or (lat >= 53.6 and lon >= 9) 
                or (lat >= 54 and lon >= 7)):
            zone = 3  # EAST
        elif ((50.97 <= lat <= 52.0 and 5.86 <= lon <= 9)
                or (49.54 <= lat <= 50.78 and 6.05 <= lon <= 7.72)
                or (49 <= lat <= 51)):
            zone = 2  # WEST
        else:
            zone = 1  # NORTH-WEST
        # Refinements
        if zone == 2:
            if (lat >= 51.1 and lon >= 7.8) or (lon > 9):
                zone = 1 # NORTH-WEST
        if zone == 1 and lat < 50.7:
            zone = 4 # SOUTH
        if zone == 4 and lat >= 49 and lon <= 8.1:
            zone = 2 # WEST
        return zone