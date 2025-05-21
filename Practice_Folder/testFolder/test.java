class StringReverser {

    public static String reverseString(String input) {
        return new StringBuilder(input).reverse().toString();
    }

    public static void main(String[] args) {
        String original = "hello";
        String reversed = reverseString(original);
        System.out.println("Original: " + original);
        System.out.println("Reversed: " + reversed);
    }
}
