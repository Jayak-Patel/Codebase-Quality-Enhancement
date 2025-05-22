import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Utility class for reversing strings.
 */
public class StringReverser {

    private static final Logger logger = LoggerFactory.getLogger(StringReverser.class);

    /**
     * Reverses the input string.
     *
     * @param str The string to reverse.  Cannot be null or empty.
     * @return The reversed string.
     * @throws IllegalArgumentException if the input string is null.
     */
    public static String reverseString(String str) {
        if (str == null) {
            logger.error("Input string cannot be null.");
            throw new IllegalArgumentException("Input string cannot be null.");
        }

        //Empty strings are already reversed. Return as is.
        if (str.isEmpty()) {
            logger.warn("Input string is empty.  Returning as is.");
            return str;
        }

        return new StringBuilder(str).reverse().toString();
    }

    /**
     * Main method demonstrating the string reversal functionality.
     *
     * @param args Command line arguments (not used).
     */
    public static void main(String[] args) {
        String input = "hello";
        String reversed = reverseString(input);

        System.out.println("Original: " + input);
        System.out.println("Reversed: " + reversed);

        logger.info("Original string: {}, Reversed string: {}", input, reversed); // Example usage of logger

        //Demonstrate empty and null string handling
        String emptyString = "";
        String reversedEmpty = reverseString(emptyString);
        System.out.println("Original empty String: " + emptyString + ", Reversed Empty String: " + reversedEmpty);

        try {
            String nullString = null;
            String reversedNull = reverseString(nullString);
            System.out.println("Reversed null string: " + reversedNull); // This line will not be reached
        } catch (IllegalArgumentException e) {
            System.err.println("Error reversing null string: " + e.getMessage()); //Handle null String input
        }
    }
}
