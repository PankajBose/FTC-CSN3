package csn.solr.morphline;

import com.google.common.collect.ListMultimap;
import org.kitesdk.morphline.api.Record;
import org.w3c.dom.*;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMResult;
import javax.xml.transform.stream.StreamSource;
import java.io.ByteArrayInputStream;
import java.io.FileReader;
import java.util.*;

public class MorphlineUtility {
    private static final String TYPE_KEY = "_type_s_";
    private static final String JSON_TYPE_KEY = "type_s";
    private static final String CHILD_DOCUMENT_KEY = "_loadSolr_childDocuments";
    private static final String PRIMARY_KEY = "documentid";

    public static Record createRecord(Record record, String mappingFile) throws Exception {
        Record jsonRecord = new Record();

        Properties properties = new Properties();
        properties.load(new FileReader(mappingFile));

        Set<String> childKeys = findChildElements(properties);

        String type = (String) properties.get(TYPE_KEY);
        jsonRecord.put(JSON_TYPE_KEY, type);

        ListMultimap<String, Object> fields = record.getFields();
        for (String key : fields.keySet()) {
            if ("timestamp".equals(key)) continue;

            String solrKey = (String) properties.get(key);
            if (solrKey == null) {
                if (!childKeys.contains(key)) {
                    System.err.println("mapping not found for " + key);
                    continue;
                }

                List<Record> childRecords = createRecord((String) record.getFirstValue(key), properties, key, (String) record.getFirstValue(PRIMARY_KEY));
                if (childRecords != null) for (Record childRecord : childRecords) {
                    jsonRecord.put(CHILD_DOCUMENT_KEY, childRecord);
                }

                continue;
            }

            jsonRecord.put(solrKey, record.getFirstValue(key));
        }

        return jsonRecord;
    }

    private static List<Record> createRecord(String xmlString, Properties properties, String key, String primaryKey) throws Exception {
        List<Map<String, String>> xml = extractDataFromXML(xmlString);
        List<Record> records = new ArrayList<>();
        int index = 0;
        for (Map<String, String> map : xml) {
            Record record = new Record();
            String type = (String) properties.get(key + "." + TYPE_KEY);
            record.put(JSON_TYPE_KEY, type);
            record.put(PRIMARY_KEY, primaryKey + "_" + type + "_" + index++);

            for (String xmlKey : map.keySet()) {
                String propertyKey = key + "." + xmlKey;
                String propertyValue = (String) properties.get(propertyKey);
                if (propertyValue == null) {
                    System.err.println("mapping not found for " + propertyKey);
                    continue;
                }

                record.put(propertyValue, map.get(xmlKey));
            }

            if (!record.getFields().isEmpty()) records.add(record);
        }

        return records;
    }

    private static Set<String> findChildElements(Properties properties) {
        Set<String> childXms = new HashSet<>();

        for (Object key : properties.keySet()) {
            String keyString = key.toString();
            if (!keyString.contains(".")) continue;

            String firstPart = keyString.substring(0, keyString.indexOf('.'));
            childXms.add(firstPart);
        }

        return childXms;
    }

    private static List<Map<String, String>> extractDataFromXML(String xml) throws Exception {
        byte[] xmlData = xml.getBytes();

        ByteArrayInputStream stream = new ByteArrayInputStream(xmlData);
        StreamSource source = new StreamSource(stream);
        DocumentBuilderFactory builderFactory = DocumentBuilderFactory.newInstance();
        DocumentBuilder builder = builderFactory.newDocumentBuilder();
        Document dom = builder.newDocument();
        DOMResult result = new DOMResult(dom);
        TransformerFactory tFactory = TransformerFactory.newInstance();
        Transformer transformer = tFactory.newTransformer();
        transformer.transform(source, result);

        Element root = dom.getDocumentElement();
        String rootName = root.getNodeName();
        NodeList childNodes = root.getChildNodes();
        int count = childNodes.getLength();
        List<Map<String, String>> data = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            Node intermediateNode = childNodes.item(i);
            if (!(intermediateNode instanceof Element)) continue;

            Map<String, String> elementData = new LinkedHashMap<>();
            Element intermediateElement = (Element) intermediateNode;
            String intermediateName = intermediateElement.getNodeName();
            NamedNodeMap attributes = intermediateElement.getAttributes();
            int attributeLength = attributes.getLength();
            for (int j = 0; j < attributeLength; j++) {
                Attr attr = (Attr) attributes.item(j);
                elementData.put(rootName + "." + intermediateName + "." + attr.getName(), attr.getValue().trim());
            }

            NodeList elementNodes = intermediateNode.getChildNodes();
            int elementCount = elementNodes.getLength();
            for (int j = 0; j < elementCount; j++) {
                Node leafNode = elementNodes.item(j);
                if (!(leafNode instanceof Element)) continue;

                Element leafElement = (Element) leafNode;
                String name = leafElement.getNodeName();
                String value = leafElement.getTextContent();
                if (value != null && value.trim().length() > 0)
                    elementData.put(rootName + "." + intermediateName + "." + name, value.trim());
            }

            if (!elementData.isEmpty()) data.add(elementData);
        }

        return data;
    }
}