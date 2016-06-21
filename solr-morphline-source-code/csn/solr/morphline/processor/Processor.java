package csn.solr.morphline.processor;

import org.kitesdk.morphline.api.Record;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMResult;
import javax.xml.transform.stream.StreamSource;
import java.io.FileInputStream;
import java.util.ArrayList;
import java.util.List;

public class Processor {
    private List<IProcessor> processorMap = new ArrayList<>();

    public Processor(String processorXML) throws Exception {
        FileInputStream stream = new FileInputStream(processorXML);
        StreamSource source = new StreamSource(stream);
        DocumentBuilderFactory builderFactory = DocumentBuilderFactory.newInstance();
        DocumentBuilder builder = builderFactory.newDocumentBuilder();
        Document dom = builder.newDocument();
        DOMResult result = new DOMResult(dom);
        TransformerFactory tFactory = TransformerFactory.newInstance();
        Transformer transformer = tFactory.newTransformer();
        transformer.transform(source, result);
        Element root = dom.getDocumentElement();

        NodeList processorNodeList = root.getElementsByTagName("processor");
        int length = processorNodeList.getLength();
        for (int i = 0; i < length; i++) {
            Element processorElement = (Element) processorNodeList.item(i);
            String name = processorElement.getAttribute("name");
            String clazz = processorElement.getAttribute("class");
            IProcessor processor = (IProcessor) Class.forName(clazz).newInstance();
            processor.setProcessorName(name);

            NodeList configNodeList = processorElement.getElementsByTagName("config");
            if (configNodeList.getLength() > 0) {
                Element configElement = (Element) configNodeList.item(0);
                NodeList paramNodeList = configElement.getElementsByTagName("param");
                int paramLength = paramNodeList.getLength();
                for (int j = 0; j < paramLength; j++) {
                    Element paramElement = (Element) paramNodeList.item(j);
                    String paramName = paramElement.getAttribute("name");
                    String paramValue = paramElement.getAttribute("value");
                    ParamType paramType = ParamType.valueOf(paramElement.getAttribute("type").toUpperCase());
                    processor.setParam(paramName, paramValue, paramType);
                }
            }
            processorMap.add(processor);
        }
    }

    public void process(Record record) {
        for (IProcessor processor : processorMap) {
            processor.process(record);
        }
    }
}