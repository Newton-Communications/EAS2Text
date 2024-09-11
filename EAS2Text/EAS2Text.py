# Standard Library
from datetime import datetime as DT
from json import loads, load
from time import localtime, timezone
from collections import Counter
from importlib import resources

# Third-Party
import requests

class InvalidSAME(Exception):
    def __init__(self, error, message="Invalid Data in SAME Message"):
        self.message = message
        self.error = error
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message}: {self.error}"


class MissingSAME(Exception):
    def __init__(self, message="Missing SAME Message"):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message}"


class EAS2Text(object):
    try:
        same_us = requests.get("https://matra.site/cdn/E2T/same-us.json").json()
    except requests.exceptions.RequestException:
        with resources.open_text('EAS2Text', 'same-us.json') as json_file:
                same_us = load(json_file)

    try:
        wfo_us = requests.get("https://matra.site/cdn/E2T/wfo-us.json").json()
    except requests.exceptions.RequestException:
        with resources.open_text('EAS2Text', 'wfo-us.json') as json_file:
                wfo_us = load(json_file)

    try:
        ccl_us = requests.get("https://matra.site/cdn/E2T/CCL-us.json").json()
    except requests.exceptions.RequestException:
        with resources.open_text('EAS2Text', 'CCL-us.json') as json_file:
                ccl_us = load(json_file)
        
    def __init__(
        self, sameData: str, timeZone: int = None, mode: str = "NONE", newWFO: bool = False,
    ) -> None:
        sameData = (
            sameData.strip()
        )  ## Strip to get rid of leading / trailing newlines and spaces (You're welcome, Don / Kane.)
        stats = self.same_us
        locality2 = self.wfo_us
        ccl2 = self.ccl_us
        self.FIPS = []
        self.FIPSText = []
        self.strFIPS = ""
        self.EASData = sameData

        # Fox 1
        if not newWFO:

            self.WFO = []
            self.WFOText = []

            ## CHECKING FOR VALID SAME
            if sameData == "":
                raise MissingSAME()
            elif sameData.startswith("NNNN"):
                self.EASText = "End Of Message"
                return
            elif not sameData.startswith("ZCZC"):
                raise InvalidSAME(sameData, message='"ZCZC" Start string missing')
            else:
                eas = "".join(
                    sameData.replace("ZCZC-", "").replace("+", "-")
                ).split("-")
                eas.remove("")

                for i in eas[2:-3]:
                    try:
                        assert len(i) == 6
                        assert self.__isInt__(i) == True
                        ## FIPS CODE
                        if i not in self.FIPS:
                            self.FIPS.append(str(i))
                    except AssertionError:
                        raise InvalidSAME("Invalid codes in FIPS data")

                for i in sorted(self.FIPS):
                    try:
                        subdiv = stats["SUBDIV"][i[0]]
                        same = stats["SAME"][i[1:]]
                        self.FIPSText.append(
                            f"{subdiv + ' ' if subdiv != '' else ''}{same}" 
                        )
                        
                        try:
                            if(str(eas[0]) == "WXR") and ("State" not in same):
                                ## WXR LOCALITY
                                wfo = locality2["SAME"][i[1:]][0]["wfo"]
                                if wfo:
                                    self.WFOText.append(
                                        f"{wfo}"
                                    )
                                    self.WFO.append(
                                        f"{wfo}"
                                    )
                                else:
                                    self.WFO.append(f"Unknown WFO for FIPS Code {i}")
                                    self.WFOText.append(f"Unknown WFO for FIPS Code {i}")
                        except KeyError:
                            self.WFO.append(f"Unknown WFO for FIPS Code {i}")
                            self.WFOText.append(f"Unknown WFO for FIPS Code {i}")
                        except Exception as E:
                            raise InvalidSAME(
                                self.WFOText, message=f"Error in WFO Text ({str(E)})"
                            )
                        
                    except KeyError:
                        self.FIPSText.append(f"FIPS Code {i}")
                        self.WFO.append(f"Unknown WFO for FIPS Code {i}")
                        self.WFOText.append(f"Unknown WFO for FIPS Code {i}")
                        
                    except Exception as E:
                        raise InvalidSAME(
                            self.FIPS, message=f"Error in FIPS Code ({str(E)})"
                        )
                    
                if len(self.FIPSText) > 1:
                    FIPSText = self.FIPSText
                    FIPSText[-1] = f"and {FIPSText[-1]}"
                self.strFIPS = "; ".join(self.FIPSText).strip() + ";"

                ## WXR LOCALITY MULTIPLE
                if(str(eas[0]) == "WXR"):
                    if self.WFOText != "":
                        if len(self.WFOText) > 1:
                            p = []
                            for values in self.WFOText:
                                if values not in p:
                                    p.append(values)
                            if(len(p) > 1):
                                p[-1] = f"and {p[-1]}"
                            self.WFOText = "; ".join(p).strip() + ";"
                        else:
                            p = self.WFOText[0]
                            self.WFOText = str(self.WFOText[0])+";"
                    if self.WFO != "":
                        if len(self.WFO) > 1:
                            p = []
                            for values in self.WFO:
                                if values not in p:
                                    p.append(values)
                            if(len(p) > 1):
                                p[-1] = f"and {p[-1]}"
                            self.WFO = "; ".join(p).strip() + ";"
                        else:
                            p = self.WFO[0]
                            self.WFO = str(self.WFO[0])+";"
            

            ## TIME CODE
            try:
                self.purge = [eas[-3][:2], eas[-3][2:]]
            except IndexError:
                raise InvalidSAME(self.purge, message="Purge Time not HHMM.")
            self.timeStamp = eas[-2]
            utc = DT.utcnow()
            if timeZone == None:
                dtOffset = utc.timestamp() - DT.now().timestamp()
            else:
                dtOffset = -timeZone * 3600

            try:
                alertStartEpoch = (
                    DT.strptime(self.timeStamp, "%j%H%M")
                    .replace(year=utc.year)
                    .timestamp()
                )
            except ValueError:
                raise InvalidSAME(
                    self.timeStamp, message="Timestamp not JJJHHMM."
                )
            alertEndOffset = (int(self.purge[0]) * 3600) + (
                int(self.purge[1]) * 60
            )
            alertEndEpoch = alertStartEpoch + alertEndOffset

            try:
                self.startTime = DT.fromtimestamp(alertStartEpoch - dtOffset)
                self.endTime = DT.fromtimestamp(alertEndEpoch - dtOffset)
                if self.startTime.day == self.endTime.day:
                    self.startTimeText = self.startTime.strftime("%I:%M %p")
                    self.endTimeText = self.endTime.strftime("%I:%M %p")
                elif self.startTime.year == self.endTime.year:
                    self.startTimeText = self.startTime.strftime(
                        "%I:%M %p %B %d"
                    )
                    self.endTimeText = self.endTime.strftime("%I:%M %p %B %d")
                else:
                    self.startTimeText = self.startTime.strftime(
                        "%I:%M %p %B %d, %Y"
                    )
                    self.endTimeText = self.endTime.strftime(
                        "%I:%M %p %B %d, %Y"
                    )
            except Exception as E:
                raise InvalidSAME(
                    self.timeStamp,
                    message=f"Error in Time Conversion ({str(E)})",
                )

            ## ORG / EVENT CODE
            try:
                self.org = str(eas[0])
                self.evnt = str(eas[1])
                try:
                    assert len(eas[0]) == 3
                except AssertionError:
                    raise InvalidSAME("Originator is an invalid length")
                try:
                    assert len(eas[1]) == 3
                except AssertionError:
                    raise InvalidSAME("Event Code is an invalid length")
                try:
                    self.orgText = stats["ORGS"][self.org]
                except:
                    self.orgText = (
                        f"An Unknown Originator ({self.org});"
                    )
                try:
                    self.evntText = stats["EVENTS"][self.evnt]
                except:
                    self.evntText = f"an Unknown Event ({self.evnt})"
            except Exception as E:
                raise InvalidSAME(
                    [self.org, self.evnt],
                    message=f"Error in ORG / EVNT Decoding ({str(E)})",
                )

            ## CALLSIGN CODE"
            self.callsign = eas[-1].strip()

            ## FINAL TEXT
            if mode == "TFT":
                self.strFIPS = (
                    self.strFIPS[:-1]
                    .replace(",", "")
                    .replace(";", ",")
                    .replace("FIPS Code", "AREA")
                )
                self.startTimeText = self.startTime.strftime(
                    "%I:%M %p ON %b %d, %Y"
                )
                self.endTimeText = (
                    self.endTime.strftime("%I:%M %p")
                    if self.startTime.day == self.endTime.day
                    else self.endTime.strftime("%I:%M %p ON %b %d, %Y")
                )
                if self.org == "EAS" or self.evnt in ["NPT", "EAN"]:
                    self.EASText = f"{self.evntText} has been issued for the following counties/areas: {self.strFIPS} at {self.startTimeText} effective until {self.endTimeText}. message from {self.callsign}.".upper()
                else:
                    self.EASText = f"{self.orgText} has issued {self.evntText} for the following counties/areas: {self.strFIPS} at {self.startTimeText} effective until {self.endTimeText}. message from {self.callsign}.".upper()

            elif mode.startswith("SAGE"):
                if self.org == "CIV":
                    self.orgText = "The Civil Authorities"
                self.strFIPS = self.strFIPS[:-1].replace(";", ",")
                self.startTimeText = self.startTime.strftime(
                    "%I:%M %p"
                ).lower()
                self.endTimeText = self.endTime.strftime("%I:%M %p").lower()
                if self.startTime.day != self.endTime.day:
                    self.startTimeText += self.startTime.strftime(" %a %b %d")
                    self.endTimeText += self.endTime.strftime(" %a %b %d")
                if mode.endswith("DIGITAL"):
                    self.EASText = f"{self.orgText} {'have' if self.org == 'CIV' else 'has'} issued {self.evntText} for {self.strFIPS} beginning at {self.startTimeText} and ending at {self.endTimeText} ({self.callsign})"
                else:
                    if self.org == "EAS":
                        self.orgText = "A Broadcast station or cable system"
                    self.EASText = f"{self.orgText} {'have' if self.org == 'CIV' else 'has'} issued {self.evntText} for {self.strFIPS} beginning at {self.startTimeText} and ending at {self.endTimeText} ({self.callsign})"

            elif mode in ["TRILITHIC", "VIAVI", "EASY"]:
                self.strFIPS = (
                    self.strFIPS[:-1]
                    .replace(",", "")
                    .replace("; ", " - ")
                    .replace("and ", "")
                    if "000000" not in self.FIPS
                    else "The United States"
                )
                if self.strFIPS == "The United States":
                    bigFips = "for"
                else:
                    bigFips = "for the following counties:"
                self.startTimeText = ""
                self.endTimeText = self.endTime.strftime(
                    "%m/%d/%y %H:%M:00 "
                ) + self.getTZ(dtOffset)
                if self.org == "CIV":
                    self.orgText = "The Civil Authorities"
                self.EASText = f"{self.orgText} {'have' if self.org == 'CIV' else 'has'} issued {self.evntText} {bigFips} {self.strFIPS}. Effective Until {self.endTimeText}. ({self.callsign})"

            elif mode in ["BURK"]:
                if self.org == "EAS":
                    self.orgText = "A Broadcast station or cable system"
                elif self.org == "CIV":
                    self.orgText = "The Civil Authorities"
                elif self.org == "WXR":
                    self.orgText = "The National Weather Service"
                self.strFIPS = (
                    self.strFIPS[:-1].replace(",", "").replace(";", ",")
                )
                self.startTimeText = (
                    self.startTime.strftime("%B %d, %Y").upper()
                    + " at "
                    + self.startTime.strftime("%I:%M %p")
                )
                self.endTimeText = self.endTime.strftime("%I:%M %p, %B %d, %Y")
                self.evntText = " ".join(self.evntText.split(" ")[1:]).upper()
                self.EASText = f"{self.orgText} has issued {self.evntText} for the following counties/areas: {self.strFIPS} on {self.startTimeText} effective until {self.endTimeText}."

            elif mode in ["DAS", "DASDEC", "MONROE"]:
                self.orgText = self.orgText.upper()
                self.evntText = self.evntText.upper()
                self.startTimeText = self.startTime.strftime(
                    "%I:%M %p ON %b %d, %Y"
                ).upper()
                self.endTimeText = self.endTime.strftime(
                    "%I:%M %p %b %d, %Y"
                ).upper()
                self.EASText = f"{self.orgText} HAS ISSUED {self.evntText} FOR THE FOLLOWING COUNTIES/AREAS: {self.strFIPS} AT {self.startTimeText} EFFECTIVE UNTIL {self.endTimeText}. MESSAGE FROM {self.callsign.upper()}."

            else:
                if self.org == "WXR":
                    if self.WFOText == "Unknown WFO;":
                        self.orgText = "The National Weather Service"
                    else:
                        self.orgText = f"The National Weather Service in {self.WFOText}"
                self.EASText = f"{self.orgText} has issued {self.evntText} for {self.strFIPS} beginning at {self.startTimeText} and ending at {self.endTimeText}. Message from {self.callsign}."
        else:

            # Function to get WFO details for a given WFO number
            def get_wfo_details(wfo_number):
                wfo_info = ccl2["WFOs"].get(wfo_number, [])
                if not wfo_info:
                    return None
                
                return {
                    "Forecast_office": wfo_info[0]["Forecast_office"],
                    "State": wfo_info[0]["State"],
                    "Office_call_sign": wfo_info[0]["Office_call_sign"],
                    "Address": wfo_info[0]["Address"],
                    "Phone_number": wfo_info[0]["PNum"]
                }

            # Parsing the JSON data
            parsed_data = {}

            for fips_code, entries in ccl2["SAME"].items():
                wfo_list = []
                nwr_freq = []
                nwr_callsign = []
                nwr_pwr = []
                nwr_sitename = []
                nwr_siteloc = []
                nwr_sitestate = []
                nwr_lat = []
                nwr_lon = []
                
                # Set to track combinations of frequency, callsign, and power to avoid duplicates
                freq_callsign_pwr_set = set()
                
                # Set to track combinations of sitename and siteloc to avoid duplicates
                sitename_siteloc_set = set()
                
                for entry in entries:
                    wfo_number = entry["WFO"]
                    
                    # Get the WFO details
                    wfo_details = get_wfo_details(wfo_number)
                    if wfo_details and wfo_details not in wfo_list:
                        wfo_list.append(wfo_details)
                    
                    # Check for duplicates based on frequency, callsign, and power
                    freq_callsign_pwr_pair = (entry["FREQ"], entry["CALLSIGN"], entry["PWR"])
                    if freq_callsign_pwr_pair not in freq_callsign_pwr_set:
                        freq_callsign_pwr_set.add(freq_callsign_pwr_pair)
                        nwr_freq.append(entry["FREQ"])
                        nwr_callsign.append(entry["CALLSIGN"])
                        nwr_pwr.append(entry["PWR"])
                    
                    # Check for duplicates based on sitename and siteloc
                    sitename_siteloc_pair = (entry["SITENAME"], entry["SITELOC"])
                    if sitename_siteloc_pair not in sitename_siteloc_set:
                        sitename_siteloc_set.add(sitename_siteloc_pair)
                        nwr_sitename.append(entry["SITENAME"])
                        nwr_siteloc.append(entry["SITELOC"])
                        nwr_sitestate.append(entry["SITESTATE"])
                    
                    if entry["LAT"] not in nwr_lat:
                        nwr_lat.append(entry["LAT"])
                    if entry["LON"] not in nwr_lon:
                        nwr_lon.append(entry["LON"])
                
                # Combine NWR data into semicolon-separated strings
                parsed_data[fips_code] = {
                    "WFOs": wfo_list,
                    "NWR_FREQ": "; ".join(nwr_freq),
                    "NWR_CALLSIGN": "; ".join(nwr_callsign),
                    "NWR_PWR": "; ".join(nwr_pwr),
                    "NWR_SITENAME": "; ".join(nwr_sitename),
                    "NWR_SITELOC": "; ".join(nwr_siteloc),
                    "NWR_SITESTATE": "; ".join(nwr_sitestate),
                    # Updated NWR_SITE logic to avoid duplicate site name and site location
                    "NWR_SITE": "; ".join(f"{siteName}, {siteState} ({siteLoc})" for siteName, siteLoc, siteState in zip(nwr_sitename, nwr_siteloc, nwr_sitestate)),
                    "NWR_COORDINATES": "; ".join(f"{lat}, {lon}" for lat, lon in zip(nwr_lat, nwr_lon))
                }


            self.WFO = []
            self.WFOText = []
            self.WFOForecastOffice = []
            self.WFOAddress = []
            self.WFOCallsign = []
            self.WFOPhoneNumber = []
            self.NWR_FREQ = []
            self.NWR_CALLSIGN = []
            self.NWR_PWR = []
            self.NWR_SITENAME = []
            self.NWR_SITELOC = []
            self.NWR_SITESTATE = []
            self.NWR_SITE = []
            self.NWR_COORDINATES = []

            ## CHECKING FOR VALID SAME
            if sameData == "":
                raise MissingSAME()
            elif sameData.startswith("NNNN"):
                self.EASText = "End Of Message"
                return
            elif not sameData.startswith("ZCZC"):
                raise InvalidSAME(sameData, message='"ZCZC" Start string missing')
            else:
                eas = "".join(
                    sameData.replace("ZCZC-", "").replace("+", "-")
                ).split("-")
                eas.remove("")

                for i in eas[2:-3]:
                    try:
                        assert len(i) == 6
                        assert self.__isInt__(i) == True
                        ## FIPS CODE
                        if i not in self.FIPS:
                            self.FIPS.append(str(i))
                    except AssertionError:
                        raise InvalidSAME("Invalid codes in FIPS data")

                for i in sorted(self.FIPS):
                    try:
                        subdiv = stats["SUBDIV"][i[0]]
                        same = stats["SAME"][i[1:]]
                        self.FIPSText.append(
                            f"{subdiv + ' ' if subdiv != '' else ''}{same}" 
                        )
                        
                        try:
                            if(str(eas[0]) == "WXR") and ("State" not in same):
                                wfolist = parsed_data[i[1:]]["WFOs"]

                                for wfos in wfolist:
                                    if wfos:
                                        ## WXR LOCALITY
                                        self.WFOText.append(
                                            f'{wfos["Forecast_office"]}, {wfos["State"]} ({wfos["Office_call_sign"]})'
                                        )

                                        self.WFO.append(
                                            f'{wfos["Forecast_office"]}, {wfos["State"]} ({wfos["Office_call_sign"]})'
                                        )

                                        self.WFOForecastOffice.append(
                                            f'{wfos["Forecast_office"]}'
                                        )
                                        
                                        self.WFOAddress.append(
                                            f'{wfos["Address"]}'
                                        )

                                        self.WFOCallsign.append(
                                            f'{wfos["Office_call_sign"]}'
                                        )

                                        self.WFOPhoneNumber.append(
                                            f'{wfos["Phone_number"]}'
                                        )

                                        self.NWR_FREQ.append(
                                            f'{parsed_data[i[1:]]["NWR_FREQ"]}'
                                        )

                                        self.NWR_CALLSIGN.append(
                                            f'{parsed_data[i[1:]]["NWR_CALLSIGN"]}'
                                        )

                                        self.NWR_PWR.append(
                                            f'{parsed_data[i[1:]]["NWR_PWR"]}'
                                        )

                                        self.NWR_SITENAME.append(
                                            f'{parsed_data[i[1:]]["NWR_SITENAME"]}'
                                        )

                                        self.NWR_SITELOC.append(
                                            f'{parsed_data[i[1:]]["NWR_SITELOC"]}'
                                        )

                                        self.NWR_SITESTATE.append(
                                            f'{parsed_data[i[1:]]["NWR_SITESTATE"]}'
                                        )

                                        self.NWR_SITE.append(
                                            f'{parsed_data[i[1:]]["NWR_SITE"]}'
                                        )

                                        self.NWR_COORDINATES.append(
                                            f'{parsed_data[i[1:]]["NWR_COORDINATES"]}'
                                        )

                                    else:
                                        self.WFO.append(f"Unknown WFO for FIPS Code {i}")
                                        self.WFOText.append(f"Unknown WFO for FIPS Code {i}")
                        except KeyError:
                            try:
                                if(str(eas[0]) == "WXR") and ("State" not in same):
                                    ## WXR LOCALITY
                                    wfo = locality2["SAME"][i[1:]][0]["wfo"]
                                    if wfo:
                                        self.WFOText.append(
                                            f"{wfo}"
                                        )
                                        self.WFO.append(
                                            f"{wfo}"
                                        )
                                    else:
                                        self.WFO.append(f"Unknown WFO for FIPS Code {i}")
                                        self.WFOText.append(f"Unknown WFO for FIPS Code {i}")
                            except KeyError:
                                self.WFO.append(f"Unknown WFO for FIPS Code {i}")
                                self.WFOText.append(f"Unknown WFO for FIPS Code {i}")
                            except Exception as E:
                                raise InvalidSAME(
                                    self.WFOText, message=f"Error in WFO Text ({str(E)})"
                                )
                            
                        except Exception as E:
                            raise InvalidSAME(
                                self.WFOText, message=f"Error in WFO Text ({str(E)})"
                            )
                        
                    except KeyError:
                        self.FIPSText.append(f"FIPS Code {i}")
                        self.WFO.append(f"Unknown WFO for FIPS Code {i}")
                        self.WFOText.append(f"Unknown WFO for FIPS Code {i}")
                        
                    except Exception as E:
                        raise InvalidSAME(
                            self.FIPS, message=f"Error in FIPS Code ({str(E)})"
                        )
                    
                if len(self.FIPSText) > 1:
                    FIPSText = self.FIPSText
                    FIPSText[-1] = f"and {FIPSText[-1]}"
                self.strFIPS = "; ".join(self.FIPSText).strip() + ";"

                ## WXR LOCALITY MULTIPLE
                if(str(eas[0]) == "WXR"):
                    if self.WFOText != "":
                        if len(self.WFOText) > 1:
                            p = []
                            for values in self.WFOText:
                                if values not in p:
                                    p.append(values)
                            if(len(p) > 1):
                                p[-1] = f"and {p[-1]}"
                            self.WFOText = "; ".join(p).strip() + ";"
                        else:
                            p = self.WFOText[0]
                            self.WFOText = str(self.WFOText[0])+";"
                    if self.WFO != "":
                        if len(self.WFO) > 1:
                            p = []
                            for values in self.WFO:
                                if values not in p:
                                    p.append(values)
                            if(len(p) > 1):
                                p[-1] = f"and {p[-1]}"
                            self.WFO = "; ".join(p).strip() + ";"
                        else:
                            p = self.WFO[0]
                            self.WFO = str(self.WFO[0])+";"
            

            ## TIME CODE
            try:
                self.purge = [eas[-3][:2], eas[-3][2:]]
            except IndexError:
                raise InvalidSAME(self.purge, message="Purge Time not HHMM.")
            self.timeStamp = eas[-2]
            utc = DT.utcnow()
            if timeZone == None:
                dtOffset = utc.timestamp() - DT.now().timestamp()
            else:
                dtOffset = -timeZone * 3600

            try:
                alertStartEpoch = (
                    DT.strptime(self.timeStamp, "%j%H%M")
                    .replace(year=utc.year)
                    .timestamp()
                )
            except ValueError:
                raise InvalidSAME(
                    self.timeStamp, message="Timestamp not JJJHHMM."
                )
            alertEndOffset = (int(self.purge[0]) * 3600) + (
                int(self.purge[1]) * 60
            )
            alertEndEpoch = alertStartEpoch + alertEndOffset

            try:
                self.startTime = DT.fromtimestamp(alertStartEpoch - dtOffset)
                self.endTime = DT.fromtimestamp(alertEndEpoch - dtOffset)
                if self.startTime.day == self.endTime.day:
                    self.startTimeText = self.startTime.strftime("%I:%M %p")
                    self.endTimeText = self.endTime.strftime("%I:%M %p")
                elif self.startTime.year == self.endTime.year:
                    self.startTimeText = self.startTime.strftime(
                        "%I:%M %p %B %d"
                    )
                    self.endTimeText = self.endTime.strftime("%I:%M %p %B %d")
                else:
                    self.startTimeText = self.startTime.strftime(
                        "%I:%M %p %B %d, %Y"
                    )
                    self.endTimeText = self.endTime.strftime(
                        "%I:%M %p %B %d, %Y"
                    )
            except Exception as E:
                raise InvalidSAME(
                    self.timeStamp,
                    message=f"Error in Time Conversion ({str(E)})",
                )

            ## ORG / EVENT CODE
            try:
                self.org = str(eas[0])
                self.evnt = str(eas[1])
                try:
                    assert len(eas[0]) == 3
                except AssertionError:
                    raise InvalidSAME("Originator is an invalid length")
                try:
                    assert len(eas[1]) == 3
                except AssertionError:
                    raise InvalidSAME("Event Code is an invalid length")
                try:
                    self.orgText = stats["ORGS"][self.org]
                except:
                    self.orgText = (
                        f"An Unknown Originator ({self.org});"
                    )
                try:
                    self.evntText = stats["EVENTS"][self.evnt]
                except:
                    self.evntText = f"an Unknown Event ({self.evnt})"
            except Exception as E:
                raise InvalidSAME(
                    [self.org, self.evnt],
                    message=f"Error in ORG / EVNT Decoding ({str(E)})",
                )

            ## CALLSIGN CODE"
            self.callsign = eas[-1].strip()

            ## FINAL TEXT
            if mode == "TFT":
                self.strFIPS = (
                    self.strFIPS[:-1]
                    .replace(",", "")
                    .replace(";", ",")
                    .replace("FIPS Code", "AREA")
                )
                self.startTimeText = self.startTime.strftime(
                    "%I:%M %p ON %b %d, %Y"
                )
                self.endTimeText = (
                    self.endTime.strftime("%I:%M %p")
                    if self.startTime.day == self.endTime.day
                    else self.endTime.strftime("%I:%M %p ON %b %d, %Y")
                )
                if self.org == "EAS" or self.evnt in ["NPT", "EAN"]:
                    self.EASText = f"{self.evntText} has been issued for the following counties/areas: {self.strFIPS} at {self.startTimeText} effective until {self.endTimeText}. message from {self.callsign}.".upper()
                else:
                    self.EASText = f"{self.orgText} has issued {self.evntText} for the following counties/areas: {self.strFIPS} at {self.startTimeText} effective until {self.endTimeText}. message from {self.callsign}.".upper()

            elif mode.startswith("SAGE"):
                if self.org == "CIV":
                    self.orgText = "The Civil Authorities"
                self.strFIPS = self.strFIPS[:-1].replace(";", ",")
                self.startTimeText = self.startTime.strftime(
                    "%I:%M %p"
                ).lower()
                self.endTimeText = self.endTime.strftime("%I:%M %p").lower()
                if self.startTime.day != self.endTime.day:
                    self.startTimeText += self.startTime.strftime(" %a %b %d")
                    self.endTimeText += self.endTime.strftime(" %a %b %d")
                if mode.endswith("DIGITAL"):
                    self.EASText = f"{self.orgText} {'have' if self.org == 'CIV' else 'has'} issued {self.evntText} for {self.strFIPS} beginning at {self.startTimeText} and ending at {self.endTimeText} ({self.callsign})"
                else:
                    if self.org == "EAS":
                        self.orgText = "A Broadcast station or cable system"
                    self.EASText = f"{self.orgText} {'have' if self.org == 'CIV' else 'has'} issued {self.evntText} for {self.strFIPS} beginning at {self.startTimeText} and ending at {self.endTimeText} ({self.callsign})"

            elif mode in ["TRILITHIC", "VIAVI", "EASY"]:
                self.strFIPS = (
                    self.strFIPS[:-1]
                    .replace(",", "")
                    .replace("; ", " - ")
                    .replace("and ", "")
                    if "000000" not in self.FIPS
                    else "The United States"
                )
                if self.strFIPS == "The United States":
                    bigFips = "for"
                else:
                    bigFips = "for the following counties:"
                self.startTimeText = ""
                self.endTimeText = self.endTime.strftime(
                    "%m/%d/%y %H:%M:00 "
                ) + self.getTZ(dtOffset)
                if self.org == "CIV":
                    self.orgText = "The Civil Authorities"
                self.EASText = f"{self.orgText} {'have' if self.org == 'CIV' else 'has'} issued {self.evntText} {bigFips} {self.strFIPS}. Effective Until {self.endTimeText}. ({self.callsign})"

            elif mode in ["BURK"]:
                if self.org == "EAS":
                    self.orgText = "A Broadcast station or cable system"
                elif self.org == "CIV":
                    self.orgText = "The Civil Authorities"
                elif self.org == "WXR":
                    self.orgText = "The National Weather Service"
                self.strFIPS = (
                    self.strFIPS[:-1].replace(",", "").replace(";", ",")
                )
                self.startTimeText = (
                    self.startTime.strftime("%B %d, %Y").upper()
                    + " at "
                    + self.startTime.strftime("%I:%M %p")
                )
                self.endTimeText = self.endTime.strftime("%I:%M %p, %B %d, %Y")
                self.evntText = " ".join(self.evntText.split(" ")[1:]).upper()
                self.EASText = f"{self.orgText} has issued {self.evntText} for the following counties/areas: {self.strFIPS} on {self.startTimeText} effective until {self.endTimeText}."

            elif mode in ["DAS", "DASDEC", "MONROE"]:
                self.orgText = self.orgText.upper()
                self.evntText = self.evntText.upper()
                self.startTimeText = self.startTime.strftime(
                    "%I:%M %p ON %b %d, %Y"
                ).upper()
                self.endTimeText = self.endTime.strftime(
                    "%I:%M %p %b %d, %Y"
                ).upper()
                self.EASText = f"{self.orgText} HAS ISSUED {self.evntText} FOR THE FOLLOWING COUNTIES/AREAS: {self.strFIPS} AT {self.startTimeText} EFFECTIVE UNTIL {self.endTimeText}. MESSAGE FROM {self.callsign.upper()}."

            else:
                if self.org == "WXR":
                    if self.WFOText == "Unknown WFO;":
                        self.orgText = "The National Weather Service"
                    else:
                        self.orgText = f"The National Weather Service in {self.WFOText}"
                self.EASText = f"{self.orgText} has issued {self.evntText} for {self.strFIPS} beginning at {self.startTimeText} and ending at {self.endTimeText}. Message from {self.callsign}."

    @classmethod
    def __isInt__(cls, number):
        try:
            int(number)
        except ValueError:
            return False
        else:
            return True

    @classmethod
    def getTZ(cls, tzOffset):
        tzone = int(tzOffset / 3600.0)
        locTime = localtime().tm_isdst
        TMZ = "UTC"
        if tzone == 3 and locTime > 0:
            TMZ = "ADT"
        elif tzone == 4:
            TMZ = "AST"
            if locTime > 0:
                TMZ = "EDT"
        elif tzone == 5:
            TMZ = "EST"
            if locTime > 0:
                TMZ = "CDT"
        elif tzone == 6:
            TMZ = "CST"
            if locTime > 0:
                TMZ = "MDT"
        elif tzone == 7:
            TMZ = "MST"
            if locTime > 0:
                TMZ = "PDT"
        elif tzone == 8:
            TMZ = "PST"
        return TMZ
