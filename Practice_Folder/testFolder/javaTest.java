class StringReverser {

    public static String reverseString(String str) {
        return new StringBuilder(str).reverse().toString();
    }

    public static void main(String[] args) {
        String input = "hello";
        String reversed = reverseString(input);
        System.out.println("Original: " + input);
        System.out.println("Reversed: " + reversed);
    }
}
