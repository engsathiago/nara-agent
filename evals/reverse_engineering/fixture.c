#include <stdio.h>

static int nara_fixture_transform(int value) {
    return value * 7 + 3;
}

int main(void) {
    printf("nara-fixture:%d\n", nara_fixture_transform(5));
    return 0;
}
