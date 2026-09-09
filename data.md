   ID     Category                       Site                               Task
  ━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   061    npm metadata                   npm Registry (https://             Report TypeScript’s version,
                                         registry.npmjs.org/typescript/     license, Node.js engine
                                         latest)                            requirement, unpacked size, and
                                                                            file count.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   062    Rust crate metadata            crates.io (https://crates.io/      Report Serde’s latest stable
                                         crates/serde)                      version, license, repository,
                                                                            total downloads, and recent
                                                                            downloads.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   063    .NET package metadata          NuGet (https://www.nuget.org/      Report the latest stable
                                         packages/Newtonsoft.Json)          version, owners, license, total
                                                                            downloads, and repository URL.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   064    Go module inspection           pkg.go.dev (https://pkg.go.dev/    Report the displayed module
                                         github.com/gin-gonic/gin)          version, publication date,
                                                                            license, imports count, and
                                                                            imported-by count.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   065    PHP dependency inspection      Packagist (https://                Report Monolog’s latest stable
                                         packagist.org/packages/monolog/    version, license, PHP
                                         monolog)                           requirement, and direct runtime
                                                                            dependencies.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   066    mathematical sequence reference MathWorld (https://                Report the Fibonacci recurrence,
                                         mathworld.wolfram.com/             its displayed initial conditions,
                                         FibonacciNumber.html)             first eight positive-index terms,
                                                                            and linked OEIS identifier.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   067    chemical reference data        NIST Chemistry WebBook (https://   Report water’s formula, molecular
                                         webbook.nist.gov/cgi/cbook.cgi?    weight, IUPAC InChIKey, CAS
                                         ID=C7732185&Mask=1)                number, and the CODATA experimental
                                                                            gas formation enthalpy with unit
                                                                            and reference.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   068    vehicle VIN decoding           NHTSA vPIC API (https://           Decode the supplied VIN and report
                                         vpic.nhtsa.dot.gov/api/vehicles/  make, model, model year, body
                                         DecodeVinValues/                  class, cylinders, horsepower,
                                         1HGCM82633A004352?format=json)    plant city/state/country, and
                                                                            decoding status text.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   069    IP network registration        ARIN RDAP (https://                Report the top-level network
                                         rdap.arin.net/registry/ip/        handle, name, address range, type,
                                         8.8.8.8)                          status, parent handle, and the
                                                                            registrant entity’s fn value.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   070    Unicode ideograph inspection   Unicode Unihan (https://           Report U+4E00’s glyph, decimal,
                                         www.unicode.org/cgi-bin/          UTF-8 and UTF-16 encodings, total
                                         GetUnihanData.pl?codepoint=4E00)  strokes, definition, and Mandarin,
                                                                            Japanese On, Korean, and
                                                                            Vietnamese readings.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   071    satellite catalog inspection   CelesTrak SATCAT (https://         Report the ISS record’s object
                                         celestrak.org/satcat/records.php? name/ID, NORAD ID, object type,
                                         CATNR=25544)                       OPS status code, owner, launch
                                                                            date/site, period, inclination,
                                                                            apogee, and perigee.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   072    regional calendar comparison   GOV.UK Bank Holidays (https://     For 2026, report Scotland’s 2nd
                                         www.gov.uk/bank-holidays.json)     January, Summer bank holiday, and
                                                                            St Andrew’s Day dates and bunting
                                                                            flags, then report England and
                                                                            Wales’s Summer bank holiday date.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   073    pageview time-series analysis  Wikimedia Pageviews API (https://  Report Apollo 11’s seven daily
                                         wikimedia.org/api/rest_v1/        view counts for 2025-01-01 through
                                         metrics/pageviews/per-article/    2025-01-07, their total, and the
                                         en.wikipedia.org/all-access/user/ highest-view date and count.
                                         Apollo_11/daily/20250101/20250107)
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   074    occupational profile analysis  O*NET OnLine (https://             Report the occupation title/code,
                                         www.onetonline.org/link/summary/  Bright Outlook status, Job Zone
                                         15-1252.00)                       title, annual median wage,
                                                                            employment, projected-growth
                                                                            wording/rate, and openings.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   075    collectible-card rules         Scryfall API (https://             Report Black Lotus’s name, mana
                                         api.scryfall.com/cards/named?     cost, type line, Oracle text,
                                         exact=Black%20Lotus)              reserved-list flag, and Vintage,
                                                                            Legacy, and Commander legalities.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   076    DOI metadata                   Crossref (https://                 Report title, publisher,
                                         api.crossref.org/works/10.1038/    publication date, work type, and
                                         s41586-023-06747-5)                all authors in displayed order.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   077    patent-record inspection        Google Patents (https://           Report the PageRank patent’s title,
                                         patents.google.com/patent/         publication/application numbers,
                                         US6285999B1/en)                    inventor, current/original assignees,
                                                                            priority, filing and publication
                                                                            dates, and legal status.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   078    cross-endpoint game data       PokéAPI (https://pokeapi.co/api/   Report Pikachu’s identity, dimensions,
                                         v2/pokemon/pikachu)                experience, ordered types and highest
                                                                            base stat; follow species.url for
                                                                            color, habitat, capture rate and
                                                                            generation.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   079    motor-race result analysis     Jolpica F1 API (https://           Report the 2024 Bahrain race/date/
                                         api.jolpi.ca/ergast/f1/2024/1/    circuit and winner’s driver,
                                         results/1/?format=json)            constructor, grid, laps, status and
                                                                            complete fastest-lap fields.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   080    protein-record inspection      UniProt (https://                  Report entry name, protein name,
                                         www.uniprot.org/uniprotkb/         gene, organism, sequence length,
                                         P04637/entry)                      and reviewed status.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   081    lexical-entry inspection       Wiktionary (https://               In the English algorithm entry, report
                                         en.wiktionary.org/wiki/algorithm)  the four-stage source-language chain,
                                                                            two displayed IPA forms, UK/US
                                                                            hyphenations, countability and plural.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   082    chess-game result inspection   Lichess (https://lichess.org/      Report the displayed time control and
                                         Z01xx8LK)                          rating mode, both players’ ratings and
                                                                            rating changes, result/termination,
                                                                            winner and total move count.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   083    marine taxonomy                WoRMS (https://                    Report AphiaID, scientific name with
                                         www.marinespecies.org/             authority, taxonomic status, genus,
                                         aphia.php?                         family, and which environment is
                                         p=taxdetails&id=137106)            affirmed versus struck through.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   084    exoplanet discovery record     NASA Exoplanet Archive             From Architecture & Discovery
                                         (https://                          Information, report host and planet,
                                         exoplanetarchive.ipac.caltech.e    displayed separation, planet size,
                                         du/overview/HD%20209458%20b)       method, year, reference and disposition.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   085    asteroid record                JPL Small-Body Database            Report Apophis’s full
                                         (https://ssd-api.jpl.nasa.gov/     designation, orbit class, epoch,
                                         sbdb.api?sstr=99942&phys-par=1)    absolute magnitude, diameter,
                                                                            and hazardous status.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   086    cross-endpoint tide station    NOAA (https://                     Report station ID/name, state,
          inspection                     api.tidesandcurrents.noaa.gov/     latitude, longitude, timezone and
                                         mdapi/prod/webapi/                 UTC offset; follow details.self and
                                         stations/9414290.json)            report established, origyear,
                                                                            removed, NOAA chart and meridian.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   087    river monitoring               USGS Water Data (https://          From Continuous Data, report the
                                         waterdata.usgs.gov/monitoring-     discharge and gage-height
                                         location/01646500/)                values, timestamps, units, and
                                                                            station name as displayed at run time.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   088    television-season analysis     TVMaze API (https://               For Game of Thrones season 1,
                                         api.tvmaze.com/shows/82/           report the episode count, first and
                                         episodes)                          final episode names and airdates,
                                                                            and every episode tied for the
                                                                            highest displayed average rating.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   089    postcode civic geography       postcodes.io (https://             Report the normalized postcode,
                                         api.postcodes.io/postcodes/        country, region, admin district and
                                         SW1A2AA)                           ward, parliamentary constituency,
                                                                            latitude/longitude, incode/outcode,
                                                                            and admin-district code.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   090    SI defining-constant table      BIPM (https://www.bipm.org/        Report all seven SI defining
                                         en/measurement-units/              constants with symbol, exact
                                         si-defining-constants)             numerical value and corresponding
                                                                            SI unit, plus the page’s
                                                                            uncertainty statement.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   091    cross-endpoint blockchain      Blockstream API (https://          Resolve Bitcoin block height
          record                         blockstream.info/api/              800000 to its hash, then open the
                                         block-height/800000)               block endpoint and report height,
                                                                            timestamp, transaction count, size,
                                                                            weight and Merkle root.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   092    legislative roll-call          U.S. House Clerk (https://         Report roll-call number, bill,
          inspection                     clerk.house.gov/Votes/2021369)     date/time, Congress/session, vote
                                                                            question and type, status, and the
                                                                            yea/nay/present/not-voting totals.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   093    Supreme Court case analysis    Oyez (https://www.oyez.org/        Report the Brown v. Board (I)
                                         cases/1940-1955/347us483)          docket, deciding Court, argued/
                                                                            reargued/decided dates, question,
                                                                            decision split, majority author,
                                                                            and the one-line holding directly
                                                                            below the majority-opinion label.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   094    EU regulation metadata         EUR-Lex (https://eur-              Report the GDPR document number
                                         lex.europa.eu/legal-content/EN/    and OJ citation, then open Document
                                         TXT/?uri=CELEX:32016R0679)         information and report Date of
                                                                            document, entry-into-force date,
                                                                            and application date.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   095    electricity-generation mix     NESO Carbon Intensity API          Select the returned interval from
                                         (https://api.carbonintensity.      2025-01-01T12:00Z to 12:30Z.
                                         org.uk/generation/2025-01-         Report every fuel/percentage pair
                                         01T12:00Z/2025-01-01T12:30Z)      in returned order, identify zero-
                                                                            percentage fuels, and verify the
                                                                            percentage total.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   096    medication-label lookup        DailyMed (https://                 Search LIPITOR, open the Viatris
                                         dailymed.nlm.nih.gov/dailymed/)    non-repackaged label, and report
                                                                            label/packager, initial approval,
                                                                            route, dosage form, active
                                                                            ingredient/moiety, and strengths.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   097    DNS record resolution          Google Public DNS (https://        Resolve example.com, change the RR
                                         dns.google/)                       type to MX, and report the result
                                                                            configuration, status/flags,
                                                                            question, and MX answer data.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   098    solar-lunar ephemeris          USNO Astronomical Applications     For the fixed date/coordinates,
                                         API (https://aa.usno.navy.mil/     report date/location, lunar phase,
                                         api/rstt/oneday?date=2025-06-     illumination, closest phase, and
                                         21&coords=38.9072,-77.0369)        every returned Sun/Moon event.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   099    consumer-product recall        CPSC Recall API (https://          Inspect recall 10000 and report its
          inspection                     www.saferproducts.gov/             identifiers/date/title, product and
                                         RestWebServices/Recall?            units, injuries, seller, country,
                                         RecallID=10000&format=json)        hazard, and remedy information.
  ─────  ─────────────────────────────  ─────────────────────────────────  ──────────────────────────────────
   100    earthquake impact record       USGS Earthquake Hazards            Report the Great Tohoku event header,
          inspection                     (https://earthquake.usgs.gov/      DYFI/ShakeMap intensities, Ground
                                         earthquakes/eventpage/            Failure estimates, and Origin-card
                                         official20110311054624120_30/     status, magnitude, depth, time,
                                         executive)                         and contributor.
