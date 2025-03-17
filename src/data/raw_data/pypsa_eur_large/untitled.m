% Excel-Datei einlesen
[num, ~, ~] = xlsread('nodes_agents.csv'); % Ersetze 'daten.xlsx' mit dem Dateinamen

% Nachkommastellen extrahieren
zahlen_str = strrep(cellstr(num2str(num(:,2))), '.', ','); % Komma als Dezimaltrennzeichen nutzen
nachkommastellen = cellfun(@(x) str2double(['0', regexp(x, ',(\d+)$', 'tokens', 'once')]), zahlen_str);

% Einzigartige Nachkommastellen bestimmen
unique_nachkommastellen = unique(nachkommastellen);

% Anzahl der eindeutigen Nachkommastellen ausgeben
anzahl_eindeutige = length(unique_nachkommastellen);

% Ergebnis anzeigen
disp(['Anzahl eindeutiger Nachkommastellen: ', num2str(anzahl_eindeutige)])
