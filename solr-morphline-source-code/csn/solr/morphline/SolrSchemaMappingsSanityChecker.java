package csn.solr.morphline;

import org.w3c.dom.Attr;
import org.w3c.dom.Document;
import org.w3c.dom.NodeList;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerException;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMResult;
import javax.xml.transform.stream.StreamSource;
import javax.xml.xpath.XPath;
import javax.xml.xpath.XPathConstants;
import javax.xml.xpath.XPathFactory;
import java.io.File;
import java.io.FileReader;
import java.util.Collections;
import java.util.HashSet;
import java.util.Properties;
import java.util.Set;

public class SolrSchemaMappingsSanityChecker {
    public static void main(String[] args) throws Exception {
        if (args.length != 3) {
            System.out.println("Usage: java -cp . " + SolrSchemaMappingsSanityChecker.class.getCanonicalName() + " <mapping file path> <schema file path> <processor file path>");
            return;
        }

        String mappingFile = args[0];
        String schemaFile = args[1];
        String processorFile = args[2];

        schemaFieldsDuplicateCheck(schemaFile);

        mappingFieldsDuplicateCheck(mappingFile);

        schemaFieldsNotExistInMapping(mappingFile, schemaFile, processorFile);

        mappingFieldsNotExistInSchema(mappingFile, schemaFile);

        copyFieldsShouldBeStoredFalseAndMultivalued(mappingFile, schemaFile);

        copyFieldsSourceAndDestinationShouldNotSame(mappingFile);
    }

    private static int schemaFieldsDuplicateCheck(String schemaFile) throws Exception {
        System.out.println("Checking duplicate declaration in schema...");

        Set<String> duplicateFields = new HashSet<>();
        Set<String> fields = new HashSet<>();

        Document dom = getDocumentFromFile(schemaFile);

        XPathFactory xPathfactory = XPathFactory.newInstance();
        XPath xpath = xPathfactory.newXPath();
        NodeList nodeList = (NodeList) xpath.compile("//field/@name").evaluate(dom, XPathConstants.NODESET);
        int count = nodeList.getLength();
        for (int i = 0; i < count; i++) {
            Attr item = (Attr) nodeList.item(i);
            String nodeValue = item.getNodeValue();
            if (fields.contains(nodeValue))
                duplicateFields.add(nodeValue);

            fields.add(nodeValue);
        }

        int size = duplicateFields.size();
        if (size > 0) {
            System.out.println("No of duplicate fields in schema = " + size);
            System.out.println("Duplicate fields in schema = " + duplicateFields);
        }

        System.out.println();

        return size;
    }

    private static int mappingFieldsDuplicateCheck(String mappingFile) throws Exception {
        System.out.println("Checking duplicate declaration in mapping...");

        Set<String> fields = new HashSet<>();
        Set<String> duplicateFields = new HashSet<>();

        Properties properties = new Properties();
        properties.load(new FileReader(mappingFile));

        for (String key : properties.stringPropertyNames()) {
            String field;
            if (key.endsWith("_type_s_") || key.startsWith("_copy_.")) field = key;
            else field = (String) properties.get(key);

            if (fields.contains(field))
                duplicateFields.add(field);

            fields.add(field);
        }

        int size = duplicateFields.size();
        if (size > 0) {
            System.out.println("No of duplicate fields in mapping = " + size);
            System.out.println("Duplicate fields in mapping = " + duplicateFields);
        }

        System.out.println();

        return size;
    }

    private static int schemaFieldsNotExistInMapping(String mappingFile, String schemaFile, String processorFile) throws Exception {
        System.out.println("Checking schema fields not mapped...");

        Set<String> schemaFields = getSchemaFields(schemaFile);
        Set<String> mappingFields = getMappedMappingFields(mappingFile);
        Set<String> processorCreatedFields = getProcessorCreatedFields(processorFile);
        schemaFields.removeAll(mappingFields);
        schemaFields.removeAll(processorCreatedFields);
        int size = schemaFields.size();
        if (size > 0) {
            System.out.println("No of schema fields not exist in mapping = " + size);
            System.out.println("Schema fields not exist in mapping = " + schemaFields);
        }

        System.out.println();

        return size;
    }

    private static int mappingFieldsNotExistInSchema(String mappingFile, String schemaFile) throws Exception {
        System.out.println("Checking mapped fields not exist in schema...");

        Set<String> schemaFields = getSchemaFields(schemaFile);
        Set<String> mappingFields = getMappingFields(mappingFile);

        mappingFields.removeAll(schemaFields);
        int size = mappingFields.size();
        if (size > 0) {
            System.out.println("No of mapping fields not exist in schema = " + size);
            System.out.println("Mapping fields not exist in schema = " + mappingFields);
        }

        System.out.println();

        return size;
    }

    private static int copyFieldsShouldBeStoredFalseAndMultivalued(String mappingFile, String schemaFile) throws Exception {
        System.out.println("Checking copy fields should be declared stored=\"false\" and multiValued=\"true\"...");

        Set<String> mappingCopyFields = getMappingCopyFields(mappingFile);
        Set<String> fields = new HashSet<>();
        Document dom = getDocumentFromFile(schemaFile);

        XPathFactory xPathfactory = XPathFactory.newInstance();
        XPath xpath = xPathfactory.newXPath();

        for (String copyField : mappingCopyFields) {
            String stored = (String) xpath.compile("//field[@name='" + copyField + "']/@stored").evaluate(dom, XPathConstants.STRING);
            String multiValued = (String) xpath.compile("//field[@name='" + copyField + "']/@multiValued").evaluate(dom, XPathConstants.STRING);
            if (!stored.equals("false") || !multiValued.equals("true")) fields.add(copyField);
        }
        int size = fields.size();
        if (size > 0) {
            System.out.println("No of copy fields not marked as stored false or multiValued true = " + size);
            System.out.println("Copy fields not marked as stored false or multiValued true = " + fields);
        }

        System.out.println();

        return size;
    }

    private static int copyFieldsSourceAndDestinationShouldNotSame(String mappingFile) throws Exception {
        System.out.println("Checking copy fields source and destination should not same...");

        Set<String> fields = new HashSet<>();

        Properties properties = new Properties();
        properties.load(new FileReader(mappingFile));

        for (String key : properties.stringPropertyNames()) {
            if (key.startsWith("_copy_.")) {
                String source = key.substring(7);
                String[] dest = properties.getProperty(key).split(",");
                for (String destField : dest) {
                    if (source.equals(destField)) fields.add(destField);
                }
            }
        }

        int size = fields.size();
        if (size > 0) {
            System.out.println("No of copy fields source and destination same = " + size);
            System.out.println("Copy fields source and destination same = " + fields);
        }

        System.out.println();

        return size;
    }

    private static Set<String> getMappedMappingFields(String mappingFile) throws Exception {
        Set<String> fields = new HashSet<>();

        Properties properties = new Properties();
        properties.load(new FileReader(mappingFile));

        for (String key : properties.stringPropertyNames()) {
            if (key.endsWith("_type_s_")) continue;
            else if (key.startsWith("_copy_.")) {
                fields.add(key.substring(7));
            } else fields.add((String) properties.get(key));
        }

        return fields;
    }

    private static Set<String> getMappingFields(String mappingFile) throws Exception {
        Set<String> fields = new HashSet<>();

        Properties properties = new Properties();
        properties.load(new FileReader(mappingFile));

        for (String key : properties.stringPropertyNames()) {
            if (key.endsWith("_type_s_")) continue;
            else if (key.startsWith("_copy_.")) {
                fields.add(key.substring(7));
                String values = (String) properties.get(key);
                Collections.addAll(fields, values.split(","));
            } else fields.add((String) properties.get(key));
        }

        return fields;
    }

    private static Set<String> getMappingCopyFields(String mappingFile) throws Exception {
        Set<String> fields = new HashSet<>();

        Properties properties = new Properties();
        properties.load(new FileReader(mappingFile));

        for (String key : properties.stringPropertyNames()) {
            if (key.startsWith("_copy_.")) {
                fields.add(key.substring(7));
            }
        }

        return fields;
    }

    private static Set<String> getSchemaFields(String schemaFile) throws Exception {
        Set<String> fields = new HashSet<>();

        Document dom = getDocumentFromFile(schemaFile);

        XPathFactory xPathfactory = XPathFactory.newInstance();
        XPath xpath = xPathfactory.newXPath();
        NodeList nodeList = (NodeList) xpath.compile("//field/@name").evaluate(dom, XPathConstants.NODESET);
        int count = nodeList.getLength();
        for (int i = 0; i < count; i++) {
            Attr item = (Attr) nodeList.item(i);
            String nodeValue = item.getNodeValue();
            if (nodeValue.equals("_root_") || nodeValue.equals("_version_")) continue;

            if (fields.contains(nodeValue))
                System.err.println("Duplicate field declaration " + nodeValue);
            else fields.add(nodeValue);
        }

        return fields;
    }

    private static Set<String> getProcessorCreatedFields(String processorFile) throws Exception {
        Set<String> fields = new HashSet<>();

        Document dom = getDocumentFromFile(processorFile);

        XPathFactory xPathfactory = XPathFactory.newInstance();
        XPath xpath = xPathfactory.newXPath();
        NodeList nodeList = (NodeList) xpath.compile("/processors/processor/config/param[@name='outputField']/@value").evaluate(dom, XPathConstants.NODESET);
        int count = nodeList.getLength();
        for (int i = 0; i < count; i++) {
            Attr item = (Attr) nodeList.item(i);
            String nodeValue = item.getNodeValue();
            fields.add(nodeValue);
        }

        return fields;
    }

    private static Document getDocumentFromFile(String schemaFile) throws ParserConfigurationException, TransformerException {
        StreamSource source = new StreamSource(new File(schemaFile));
        DocumentBuilderFactory builderFactory = DocumentBuilderFactory.newInstance();
        DocumentBuilder builder = builderFactory.newDocumentBuilder();
        Document dom = builder.newDocument();
        DOMResult result = new DOMResult(dom);
        TransformerFactory tFactory = TransformerFactory.newInstance();
        Transformer transformer = tFactory.newTransformer();
        transformer.transform(source, result);
        return dom;
    }
}