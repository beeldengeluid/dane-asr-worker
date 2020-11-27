import tarfile

from stat import S_ISREG, ST_CTIME, ST_MODE
import os, sys, time

from searchlayer.importer.LayerImporter import LayerImporter
from scandir import scandir
import shutil
from elasticsearch import helpers

import logging
import io

logger = logging.getLogger('searchlayerindexer')


# this class can be used to import the data on the B&G ASR server
class ASR1BestImporter(LayerImporter):

    # config contains: ASR_INPUT_DIR, ASR_EXTRACT_DIR & COLLECTION_ID
    def __init__(self, config, reconsiler, layerType='asr'):
        self.config = config
        self.reconsiler = reconsiler
        self.layerType = layerType

        # processed-asr-programs.txt is assumed to be in the ASR_EXTRACT_DIR
        self.processedCache = set()
        self.processedFile = config['PROCESSED_CACHE_FILE']
        if os.path.exists(self.processedFile):
            with open(self.processedFile, mode="r") as f:
                for line in f:
                    self.processedCache.add(line.replace('\n', ''))
	self.skipList = config['SKIP_LIST']
	with open(self.skipList, mode="r") as f:
		for line in f:
			self.processedCache.add(line.replace('\n', ''))

    def processedCacheExists(self):
        if os.path.exists(self.processedFile):
            return True
        return False

    def addProgramToCache(self, programId):
        self.processedCache.add(programId)

        with open(self.processedFile, mode="a+") as f:
            f.write(programId + "\n")

    def removeFromFileCache(self, listToBeRemoved):
        done = set()
        with open(self.processedFile, mode="r") as doneFile:
            for line in doneFile:
                done.add(line.rstrip('\n'))

        toBeRemoved = set(listToBeRemoved)

        newList = done - toBeRemoved

        # write the new list
        with open(self.processedFile, "w") as doneFile:
            for program in newList:
                doneFile.write(program + "\n")

    # Warning: overwrites old cache!
    # Call this using the ES from SearchLayerIndexer.es
    def writeESDoneList(self, es):
        self.processedCache = set()
        query = {
            "size": 100000,
            "stored_fields": [],
            "query": {
                "bool": {
                    "must": [
                        {
                            "nested": {
                                "path": "layer__asr",
                                "query": {
                                    "exists": {
                                        "field": "layer__asr"
                                    }
                                }
                            }
                        }
                    ]
                }
            }
        }
        results = helpers.scan(es,
                               query=query,
                               index="nisv-catalogue-aggr-full-18-158",
                               doc_type="program_aggr"
                               )
        with open(self.processedFile, "w") as doneFile:
            for result in results:
                self.processedCache.add(result['_id'])
                doneFile.write(result['_id'] + "\n")

    def __listDirByCreationDate(self):
        # get all entries in the directory w/ stats
        dirPath = self.config['ASR_INPUT_DIR']
        entries = (os.path.join(dirPath, fn) for fn in os.listdir(dirPath))
        entries = ((os.stat(path), path) for path in entries)

        # leave only regular files, insert creation date
        entries = ((stat[ST_CTIME], path) for stat, path in entries if S_ISREG(stat[ST_MODE]))
        # NOTE: on Windows `ST_CTIME` is a creation date
        #  but on Unix it could be something else
        # NOTE: use `ST_MTIME` to sort by a modification date

        for cdate, path in sorted(entries):
            print(time.ctime(cdate), os.path.basename(path))

    # TODO build some mechanism that just used the extracted 1Best file
    def generate(self, override=False):
        for fn in scandir(self.config['ASR_INPUT_DIR']):
            if fn.name.find('tar.gz') != -1:
                programId = fn.name[0:fn.name.find('.tar.gz')]

                # do not process the file if it was already extracted in the work dir
		if override or programId not in self.processedCache:
                    transcriptions = self.__extractASRTranscriptions(programId, fn.path)
                    if transcriptions:
                        yield {
                            'resourceId': programId,
                            'collectionId': self.config['COLLECTION_ID'],
                            'layer__%s' % self.layerType: transcriptions
                        }
		    else:
			logger.error('%s read error, no transcripts' % programId)
                else:
                    #logger.debug('%s was already processed' % programId)
		    pass

    # returns the layer mapping for the nested document
    def getLayerMapping(self):
        return {
            'words': {
                'type': 'text'
            },
            'carrierId': {
                'type': 'text'
            },
            'start': {
                'type': 'float'
            },
            'fragmentId': {
                'type': 'text'
            },
            'sequenceNr': {
                'type': 'long'
            }

        }

    def __extractASRTranscriptions(self, programId, fn):
        logger.info('extracting %s' % fn)
        extractTxtFile = '1Best.txt'
        extractCtmFile = '1Best.ctm'
        programDir = None

        with tarfile.open(fn) as tar:
            # extract the 1Best file into the extract dir
            ed = self.config['ASR_EXTRACT_DIR']
            if os.path.exists(ed):
                programDir = os.path.join(ed, programId)
                if not os.path.exists(programDir):
                    os.mkdir(programDir)
                try:
                    tar.extract(extractTxtFile, path=programDir)
                    tar.extract(extractCtmFile, path=programDir)
                except KeyError as e:
                    logger.warning('No 1Best file found!! %s' % fn)
                    return None
                except EOFError as eof:
                    logger.warning('EOF error... %s' % fn)
                    return None
		except IOError as ioe:
		    logger.error('IO error... on %s' % fn)

        # Check if programDir was initialized and read the extracted ASR file.
        transcriptions = None
        if programDir:
            try:
                with io.open(os.path.join(programDir, extractCtmFile), encoding="utf-8") as timesFile:
                    times = self.__extractTimeInfo(timesFile)

                with io.open(os.path.join(programDir, extractTxtFile), encoding="utf-8") as asrFile:
                    transcriptions = self.__parseASRResults(asrFile, times)
            except EnvironmentError as e:  # OSError or IOError...
                logger.error(os.strerror(e.errno))

            # Clean up the extracted dir
            shutil.rmtree(programDir)
            logger.info("Cleaned up folder {}".format(programDir))

        return transcriptions

    def __parseASRResults(self, asrFile, times):
        transcriptions = []
        i = 0
        curPos = 0

        for line in asrFile:
            parts = line.replace('\n', '').split("(")

            # extract the text
            words = parts[0].strip()
            numberOfWords = len(words.split(" "))
            wordTimes = times[curPos:curPos+numberOfWords]
            curPos = curPos+numberOfWords

            # Check number of words matches the number of wordTimes
            if not len(wordTimes) == numberOfWords:
                logger.warning("Number of words does not match word-times for file: {}, "
                               "current position in file: {}".format(asrFile.name, curPos))

            # extract the carrier and fragment ID
            carrier_fragid = parts[1].split(" ")[0].split(".")
            carrier = carrier_fragid[0]
            fragid = carrier_fragid[1]

            # extract the starttime
            sTime = parts[1].split(" ")[1].replace(")", "")
            sTime = sTime.split(".")
            starttime = int(sTime[0]) * 1000

            subtitle = {
                'words': unicode(words),
                'wordTimes': wordTimes,
                'start': float(starttime),
                'sequenceNr': i,
                'fragmentId': fragid,
                'carrierId': carrier
            }
            transcriptions.append(subtitle)
            i += 1
        return transcriptions

    def __extractTimeInfo(self, timesFile):
        times = []

        for line in timesFile:
            timeString = line.split(" ")[2]
            mSecValue = int(float(timeString)*1000)
            times.append(mSecValue)

        return times