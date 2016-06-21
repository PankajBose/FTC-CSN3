'\nDocument processor for extraction of entities from documents.\n\nCopyright (C) 2004-2007\nFast Search & Transfer ASA\n\n$Id$\n'
from docproc import DocumentProcessor, ProcessorStatus
from docproc import PositionTable, DocumentAttributes
from docproc import Logger, Exceptions
from docproc import ConfigurationError
from docproc.DocumentAttributes import TextChunks
import docproc
from pylib import ConfigSupportLib, StringUtils
import pyfacalib
import re

def Esc(s):
    """ Make sure the XML doesn't break when str is put in an attribute. """
    return str(s).replace('"', '"')



def BoolFlag(expression, property):
    """ Set an XML attribute, using 'yes' and 'no' for True and False. """
    return (' %s="%s"' % (property,
     ((expression and 'yes') or 'no')))



def WrapPipelineXML(name, type, replace, matcher, matcherXml, separator2, filter, rename, meta, verbose = 0, debug = 0):
    '\n    Create an XML configuration from the arguments. Either matcher (filename) or matcherXml must be specified.\n    '
    if ((not type) or (type == '')):
        stageName = ''
        update = ' update="no"'
    else:
        stageName = (' name="%s"' % Esc(type))
        update = ''
    if (not (matcher or matcherXml)):
        raise 'A filename or an XML snippet is needed to initialize the matcher.'
    if (matcher and matcherXml):
        raise 'You must specify either an XML snippet or a filename, not both.'
    if matcher:
        matcherFile = (' matcher="%s"' % matcher)
    else:
        matcherFile = ''
    matcherXml = ((matcherXml and ('<!-- matcher -->\n%s\n' % matcherXml)) or '')
    sep = ((separator2 and (' separator="%s"' % Esc(separator2))) or '')
    config = ('      <!-- stage: %s -->      <matcher type="pipeline"%s%s>        <pipeline>          <stage %s%s%s%s%s>            %s            <!-- filters -->            %s\n            <!-- rename -->            %s            <!-- meta -->            %s          </stage>        </pipeline>      </matcher>' % (name,
     BoolFlag(debug, 'debug'),
     BoolFlag(verbose, 'verbose'),
     stageName,
     update,
     BoolFlag((replace and type), 'replace'),
     matcherFile,
     sep,
     matcherXml,
     '\n'.join(map(lambda x:('<filter name="%s" predicate="%s"/>' % (Esc(x[0]),
      Esc(x[1])))
, filter.items())),
     '\n'.join(map(lambda x:('<rename from="%s" to="%s"/>' % (Esc(x[0]),
      Esc(x[1])))
, rename.items())),
     '\n'.join(map(lambda x:('<meta name="%s" value="%s"/>' % (Esc(x[0]),
      Esc(x[1])))
, meta.items()))))
    return config


class Matcher(DocumentProcessor):
    __module__ = __name__
    __doc__ = '\n    Extracts stuff somehow detected by a matcher object. Updates the dukes with\n    detailed match data for use by scope search, and also updates the document\n    with "flat" fields to be used for document-level navigators. Can also be\n    configured to update only dukes or "flat" fields, or neither.\n    '

    def ConfigurationChanged(self, attributes):
        '\n        Invoked when a parameter changes, and initially.\n        '
        self._flushed = 0
        self._argument = attributes
        self._guard = self.GetParameter('guard')
        self._dispatch = self.GetParameter('dispatch')
        self._matchers = {}
        self._phrases = {}
        self._lazy = int(self.GetParameter('lazy'))
        configurations = self.GetParameter('matcher').split()
        self._inputs = self.GetParameter('input').split()
        self._output = self.GetParameter('output').strip()
        phrases = str(self.GetParameter('phrases')).split()
        self._separator = self.GetParameter('separator')
        self._separator2 = self.GetParameter('separator2').strip()
        self._type = self.GetParameter('type').strip()
        self._context = self.GetParameter('context')
        self._debug = 0
        self._verbose = 0
        self._insert_into_duke = ((self._type is not None) and (self._type != ''))
        try:
            self._meta = dict(map(lambda x:x.split(':')
, self.GetParameter('meta').split()))
        except:
            raise ConfigurationError(("%s: Failed to parse '%s'." % (self.GetName(),
             self.GetParameter('meta'))))
        try:
            self._filter = dict(map(lambda x:x.split(':')
, self.GetParameter('filter').split()))
        except:
            raise ConfigurationError(("%s: Failed to parse '%s'." % (self.GetName(),
             self.GetParameter('filter'))))
        try:
            self._rename = dict(map(lambda x:x.split(':')
, self.GetParameter('rename').split()))
        except:
            raise ConfigurationError(("%s: Failed to parse '%s'." % (self.GetName(),
             self.GetParameter('rename'))))
        self._byteguards = {}
        try:
            fields = self.GetParameter('byteguard').split()
        except:
            fields = []
        for field in fields:
            count = field.count(':')
            if (count == 1):
                (a, b,) = tuple(field.split(':'))
                self._byteguards[a] = (int(b),
                 (int(b) + 10000))
            elif (count == 2):
                (a, b, c,) = tuple(field.split(':'))
                if (int(b) < int(c)):
                    self._byteguards[a] = (int(b),
                     int(c))
                else:
                    self._byteguards[a] = (int(c),
                     int(b))
            else:
                log(log.FLOG_WARNING, ("%s: '%s' is an invalid byte guard specification, ignoring it." % (self.GetName(),
                 field)))

        if (not self._lazy):
            connection = self.GetContainer().GetSystem().GetConfigServer()
        for configuration in configurations:
            if (configuration.find(':') == -1):
                (values, filename,) = ['*',
                 configuration]
            else:
                (values, filename,) = configuration.split(':')
            if ((not self._lazy) and log(log.FLOG_DEBUG, ("%s: creating matcher from '%s'" % (self.GetName(),
             filename)))):
                matcher = self.CreateMatcher(connection, filename)
                if (not matcher):
                    raise ConfigurationError(("%s: Failed to access or parse configuration file '%s'." % (self.GetName(),
                     filename)))
            values = map(lambda x:x.strip('{}')
, values.split(','))
            for value in values:
                self._matchers[value] = (matcher,
                 filename)


        for configuration in phrases:
            if (configuration.find(':') == -1):
                (values, phraselevel,) = ['*',
                 configuration]
            else:
                (values, phraselevel,) = configuration.split(':')
            values = map(lambda x:x.strip('{}')
, values.split(','))
            for value in values:
                self._phrases[value] = int(phraselevel)





    def CreateMatcher(self, connection, filename):
        '\n        Creates and returns a matcher object, instantiated from the given configuration file.\n        Returns None if things go awry. Also returns a flag indicating the type of the matcher,\n        so that we know what type of input to feed it.\n        '
        local = ConfigSupportLib.LocalFile(connection, 'DocumentProcessor', filename, 1)
        try:
            matcher = None
            try:
                config = WrapPipelineXML(self.GetName(), self._type, 1, local, None, self._separator2, self._filter, self._rename, self._meta, self._debug, self._verbose)
                log(log.FLOG_DEBUG, ("%s: Generated pipeline is '%s'" % (self.GetName(),
                 config)))
                matcher = pyfacalib.matcher()
                matcher.parse(config)
            except:
                log(log.FLOG_ERROR, ("%s: Failed to instantiate the matcher from '%s'." % (self.GetName(),
                 filename)))
                from pylib import StringUtils
                log(log.FLOG_ERROR, ('%s: Reason was: %s.' % (self.GetName(),
                 StringUtils.format_exc())))
                matcher = None

        finally:
            ConfigSupportLib.LocalFileCleanup(local, filename)

        return matcher



    def ByteGuardBreached(self, field, chunk_len, docid):
        """ 
        check whether the chunk length is within the given limits
        """
        (minimum, maximum,) = self._byteguards.get(field, (0,
         10000))
        if ((chunk_len < minimum) and log(log.FLOG_VERBOSE, ("%s: Document '%s': Chunk is smaller than minimum byteguard (%d < %d), skipping" % (self.GetName(),
         str(docid),
         chunk_len,
         minimum)))):
            return 1
        if ((chunk_len > maximum) and log(log.FLOG_VERBOSE, ("%s: Document '%s': Chunk is larger than maximum byteguard (%d > %d), skipping" % (self.GetName(),
         str(docid),
         chunk_len,
         maximum)))):
            return 1
        return 0



    def Process(self, docid, document):
        '\n        Updates the document with buffers of entities extracted from various\n        document fields.\n        '
        if (self._flushed and self.ConfigurationChanged(self._argument)):
            pass
        if ((self._guard and (not document.GetValue(self._guard, ''))) and document.logger.Info('The document did not pass the guard criterion, no matching performed.')):
            return ProcessorStatus.OK_NoChange
        doc = []
        raw_text_chunks = []
        for field in self._inputs:
            for (chunk, meta,) in document.GetIterator(field, 1):
                if self.ByteGuardBreached(field, len(chunk), docid):
                    continue
                if ('duke' in meta):
                    duke = meta['duke']
                    if (duke and doc.append(duke)):
                        pass
                else:
                    if ((chunk and (chunk != '')) and raw_text_chunks.append(chunk)):
                        pass


        dispatch = document.GetValue(self._dispatch, '')
        original_dispatch = dispatch
        if ((not dispatch) and document.logger.Info(("%s: The document's '%s' attribute is not set, reverting to the fallback matcher." % (self.GetName(),
         self._dispatch)))):
            pass
        if (not (dispatch in self._matchers)):
            dispatch = '*'
            if ((not (dispatch in self._matchers)) and document.logger.Info(("%s: No fallback matcher specified, no matching performed for document '%s'." % (self.GetName(),
             str(docid))))):
                return ProcessorStatus.OK_NoChange
        (matcher, filename,) = self._matchers[dispatch]
        if ((self._lazy and (not matcher)) and log(log.FLOG_DEBUG, ('%s: Lazy loading of configuration for "%s"...' % (self.GetName(),
         dispatch)))):
            connection = self.GetContainer().GetSystem().GetConfigServer()
            matcher = self.CreateMatcher(connection, filename)
            if ((not matcher) and document.logger.Warning(("%s: Failed to access or parse configuration file '%s', document will not be processed." % (self.GetName(),
             filename)))):
                return ProcessorStatus.OK_NoChange
            self._matchers[dispatch] = (matcher,
             filename)
        report_output = (self._output != '')
        language = document.GetValue('language', '')
        if ((not language) and document.logger.Info("The document's 'language' attribute is not set, reverting to default language handling.")):
            pass
        if self._context:
            context_cue = document.GetValue(self._context)
        else:
            context_cue = language
        matcher.configure(language, 'utf-8')
        keepers = []
        if (len(doc) > 0):
            try:
                keepers = matcher.process(doc, context_cue, None, report_output)
            except RuntimeError, e:
                document.logger.Warning(('%s: process() returned: %s' % (self.GetName(),
                 e)))
        if (len(raw_text_chunks) > 0):
            for chunk in raw_text_chunks:
                try:
                    new_keepers = matcher.lookup(chunk, context_cue)
                    if (report_output and keepers.extend(new_keepers)):
                        pass
                except RuntimeError, e:
                    document.logger.Warning(('%s: lookup() returned: %s' % (self.GetName(),
                     e)))

        if report_output:
            counts = {}
            for match in keepers:
                if match[2]:
                    counts[match[2]] = (counts.setdefault(match[2], 0) + 1)

            phraselevel = self._phrases.get(original_dispatch, self._phrases.get('*', 0))
            if (phraselevel > 0):
                counts = dict(filter(lambda x:(len(x[0].split()) > phraselevel)
, counts.items()))
            existing = document.GetValue((self._output + '_counts'), None)
            if existing:
                for (key, value,) in existing.items():
                    if (key in counts):
                        counts[key] += value
                    else:
                        counts[key] = value

            expanded = reduce(lambda x, y:(x + y)
, [ ([key] * value) for (key, value,) in counts.items() ], [])
            expanded.sort()
            document.Set((self._output + '_raw'), self._separator.join(expanded))
            document.Set((self._output + '_counts'), counts)
            keys = counts.keys()
            keys.sort()
            document.Set(self._output, self._separator.join(keys))
        return ProcessorStatus.OK



    def FlushState(self):
        if self._matchers:
            self._flushed = 1
            try:
                map(lambda x:x.destroy()
, self._matchers.values())
            except:
                pass
            self._matchers = {}
            log(log.FLOG_DEBUG, ('%s: Flushed all matchers.' % self.GetName()))
        return 1



class PartialMatcher(DocumentProcessor):
    __module__ = __name__
    __doc__ = '\n    Some matchers are configured to detect "full forms", e.g., "John F. Kerry" in the case of a person name matcher.\n    However, it is often the case that the full form of an entity type is only mentioned once in the document, and that\n    the most common reference to the entity is a "partial form", e.g., just "Kerry". This class looks at the entries\n    for a given entity type found in the duke, and, assuming that these are full forms, does a second pass\n    through the text to also locate the corresponding partial forms.\n\n    '

    def ConfigurationChanged(self, attributes):
        '\n        Invoked when a parameter changes, and initially.\n        '
        self._inputs = self.GetParameter('input').split()
        self._type = self.GetParameter('type')
        try:
            self._filter = dict(map(lambda x:x.split(':')
, self.GetParameter('filter').split()))
        except:
            raise ConfigurationError(("%s: Failed to parse '%s'." % (self.GetName(),
             self.GetParameter('filter'))))
        try:
            self._meta = dict(map(lambda x:x.split(':')
, self.GetParameter('meta').split()))
        except:
            raise ConfigurationError(("%s: Failed to parse '%s'." % (self.GetName(),
             self.GetParameter('meta'))))
        self._basemeta = self.GetParameter('base').strip()
        self._partialmeta = self.GetParameter('partial').strip()
        if (len(self._partialmeta.split()) > 1):
            self._partialmeta = self._partialmeta.split()[0]
            log(log.FLOG_INFO, ("%s: This partial matcher supports only one partial attribute, using '%s'." % (self.GetName(),
             self._partialmeta)))
        self._mode = self.GetParameter('mode')
        self._inherit = self.GetParameter('inherit')
        try:
            rejector = self.GetParameter('rejector')
        except:
            rejector = ''
        debug = 0
        verbose = 0
        matcher = None
        try:
            rejectorFile = None
            if rejector:
                connection = self.GetContainer().GetSystem().GetConfigServer()
                rejectorFile = ConfigSupportLib.LocalFile(connection, 'DocumentProcessor', rejector, 1)
                rejectorXml = ('<rejector filename="%s"/>' % rejectorFile)
            else:
                rejectorXml = ''
            partialXml = ('                <matcher type="partial"%s%s>\n                  <partial name="%s" base="%s" partial="%s" mode="%s"%s>\n                    %s                  </partial>\n                </matcher>' % (BoolFlag(debug, 'debug'),
             BoolFlag(verbose, 'verbose'),
             Esc(self._type),
             Esc(self._basemeta),
             Esc(self._partialmeta),
             Esc(self._mode),
             BoolFlag(self._inherit, 'inherit'),
             rejectorXml))
            matcherXml = WrapPipelineXML(self.GetName(), self._type, 1, None, partialXml, '/', self._filter, {}, self._meta, debug, verbose)
            log(log.FLOG_DEBUG, ('%s: Wrapper XML: %s:' % (self.GetName(),
             matcherXml)))
            matcher = None
            try:
                matcher = pyfacalib.matcher()
                if ((not matcher.parse(matcherXml)) and log(log.FLOG_DEBUG, ('%s: Creation of matcher failed.' % self.GetName()))):
                    matcher = None
                matcher.debug(debug, verbose)
            except:
                log(log.FLOG_ERROR, ("%s: Failed to instantiate the matcher using '%s'." % (self.GetName(),
                 filename)))

        finally:
            if (rejectorFile and ConfigSupportLib.LocalFileCleanup(rejectorFile, rejector)):
                pass

        if matcher:
            self._matcher = matcher
        else:
            raise ConfigurationError(('%s could not be initialized.' % self.GetName()))



    def Process(self, docid, document):
        '\n        Resolves partial matches.\n        '
        language = document.GetValue('language', '')
        if ((not language) and document.logger.Info("The document's 'language' attribute is not set, reverting to default language handling.")):
            pass
        context_cue = language
        self._matcher.configure(language, 'UTF-8')
        doc = []
        for field in self._inputs:
            for (chunk, meta,) in document.GetIterator(field, 1):
                if ('duke' in meta):
                    duke = meta['duke']
                    if (duke and doc.append(duke)):
                        pass


        try:
            if ((len(doc) > 0) and self._matcher.process(doc, context_cue, None, 0)):
                pass
        except RuntimeError, e:
            document.logger.Warning(('%s: process() returned: %s' % (self.GetName(),
             e)))
        return ProcessorStatus.OK



class MatchAnnotator(DocumentProcessor):
    __module__ = __name__
    __doc__ = '\n    Enables one to annotate a match, given a Python expression to evaluate.\n\n    '

    def ConfigurationChanged(self, attributes):
        '\n        Invoked when a parameter changes, and initially.\n        '
        self._inputs = self.GetParameter('input').split()
        self._type = self.GetParameter('type')
        self._attribute = self.GetParameter('attribute')
        self._initialization = self.GetParameter('initialization')
        self._environment = {}
        if self._initialization:
            try:
                exec (self._initialization,
                 globals(),
                 self._environment)
            except:
                raise ConfigurationError(("Failed to execute '%s'." % self._initialization))
            log(log.FLOG_INFO, ('%s: Initialized with "%s"' % (self.GetName(),
             self._initialization)))
        self._expression = self.GetParameter('expression')



    def Process(self, docid, document):
        '\n        Examines the position tables and possibly annotates the matches.\n        '
        if ((not self._inputs) or ((not self._type) or (not self._attribute))):
            return ProcessorStatus.OK_NoChange
        for field in self._inputs:
            for (chunk, meta,) in document.GetIterator(field, 1):
                if (not ('positions' in meta)):
                    continue
                matches = meta['positions'].GetMatches(self._type, 0)
                if (not matches):
                    continue
                for match in matches:
                    self._environment.update({'match': match[1]})
                    try:
                        annotation = eval(self._expression, globals(), self._environment)
                    except:
                        continue
                    if annotation:
                        match[1][self._attribute] = annotation



        return ProcessorStatus.OK



class MatcherReplacer(DocumentProcessor):
    __module__ = __name__
    __doc__ = '\n    Does a search-and-replace operation over a given set of fields, where the matcher dictates what we search for and replace with.\n    '

    def ConfigurationChanged(self, attributes):
        self._flushed = 0
        self._argument = attributes
        try:
            connection = self.GetContainer().GetSystem().GetConfigServer()
            filename = self.GetParameter('matcher')
            local = ConfigSupportLib.LocalFile(connection, 'DocumentProcessor', filename, 1)
            self._matcher = pyfacalib.matcher()
            self._matcher.create(local)
        except:
            log(log.FLOG_ERROR, ("%s: Failed to instantiate the matcher using '%s'." % (self.GetName(),
             filename)))
            self._matcher = None
        ConfigSupportLib.LocalFileCleanup(local, filename)
        self._dispatch = self.GetParameter('dispatch')
        self._sorted = int(self.GetParameter('sorted'))
        self._meta = int(self.GetParameter('meta'))
        try:
            mappings = self.GetParameter('mappings')
            self._mappings = map(lambda x:tuple(x.split(':'))
, mappings.split())
        except:
            log(log.FLOG_ERROR, ("%s: Failed to parse mapping specification '%s'." % (self.GetName(),
             mappings)))
            self._mappings = []



    def Process(self, docid, document):
        if (self._flushed and self.ConfigurationChanged(self._argument)):
            pass
        if (not self._matcher):
            return ProcessorStatus.OK_NoChange
        context = str(document.GetValue(self._dispatch, ''))
        for (input, output,) in self._mappings:
            chunks = TextChunks()
            for (chunk, meta,) in document.GetIterator(input, 1):
                try:
                    processed = self._matcher.replace(chunk, context, self._sorted, self._meta)
                    chunks.append(processed, {})
                except:
                    document.logger.Warning(("%s: Search and replace operation encountered problems for document '%s' for input field '%s' with context '%s'." % (self.GetName(),
                     str(docid),
                     input,
                     context)))

            document.Set(output, chunks)

        return ProcessorStatus.OK



    def FlushState(self):
        if self._matcher:
            self._flushed = 1
            try:
                self._matcher.destroy()
            except:
                pass
            log(log.FLOG_DEBUG, ('%s: Flushed matcher.' % self.GetName()))
        return 1