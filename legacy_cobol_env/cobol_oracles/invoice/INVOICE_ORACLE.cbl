       >>SOURCE FORMAT FREE
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INVOICE-ORACLE.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPUT-FILE ASSIGN TO "input.txt"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT OUTPUT-FILE ASSIGN TO "output.txt"
               ORGANIZATION IS LINE SEQUENTIAL.

       DATA DIVISION.
       FILE SECTION.
       FD INPUT-FILE.
       01 INPUT-LINE                 PIC X(44).
       FD OUTPUT-FILE.
       01 OUTPUT-LINE                PIC X(18).

       WORKING-STORAGE SECTION.
       COPY INVOICE_REC.
       COPY TAX_CODE.
       01 EOF-FLAG                   PIC X VALUE "N".
       01 WS-IDX                     PIC 9 VALUE 0.
       01 WS-ITEM-START              PIC 99 VALUE 0.
       01 WS-PRICE-START             PIC 99 VALUE 0.
       01 WS-TAX-START               PIC 99 VALUE 0.
       01 WS-QTY                     PIC 99 VALUE 0.
       01 WS-PRICE-CENTS             PIC 9(6) VALUE 0.
       01 WS-LINE-CENTS              PIC 9(9) VALUE 0.
       01 WS-TAX-CENTS               PIC 9(9) VALUE 0.
       01 WS-TAX-PERCENT             PIC 9V9999 VALUE 0.
       01 WS-TOTAL-CENTS             PIC 9(9) VALUE 0.
       01 OUTPUT-RECORD.
          05 OUT-INVOICE-ID          PIC X(6).
          05 OUT-TOTAL               PIC 9(9).
          05 OUT-ITEM-COUNT          PIC 99.
          05 OUT-FLAG                PIC X.

       PROCEDURE DIVISION.
           OPEN INPUT INPUT-FILE
           OPEN OUTPUT OUTPUT-FILE
           PERFORM UNTIL EOF-FLAG = "Y"
              READ INPUT-FILE
                 AT END
                    MOVE "Y" TO EOF-FLAG
                 NOT AT END
                    PERFORM MIGRATE-INVOICE
                    MOVE OUTPUT-RECORD TO OUTPUT-LINE
                    WRITE OUTPUT-LINE
              END-READ
           END-PERFORM
           CLOSE INPUT-FILE
           CLOSE OUTPUT-FILE
           STOP RUN.

       MIGRATE-INVOICE.
           MOVE INPUT-LINE TO INVOICE-RECORD
           MOVE ZERO TO WS-TOTAL-CENTS
           IF ITEM-COUNT > 4
              MOVE 4 TO ITEM-COUNT
           END-IF

           PERFORM VARYING WS-IDX FROM 1 BY 1 UNTIL WS-IDX > ITEM-COUNT
              COMPUTE WS-ITEM-START = 9 + ((WS-IDX - 1) * 9)
              COMPUTE WS-PRICE-START = WS-ITEM-START + 2
              COMPUTE WS-TAX-START = WS-ITEM-START + 8
              MOVE FUNCTION NUMVAL(INPUT-LINE(WS-ITEM-START:2)) TO WS-QTY
              MOVE FUNCTION NUMVAL(INPUT-LINE(WS-PRICE-START:6)) TO WS-PRICE-CENTS
              MOVE INPUT-LINE(WS-TAX-START:1) TO TAX-CODE(WS-IDX)
              COMPUTE WS-LINE-CENTS = WS-QTY * WS-PRICE-CENTS
              CALL "TAXRATE" USING TAX-CODE(WS-IDX) WS-TAX-PERCENT
              COMPUTE WS-TAX-CENTS ROUNDED = WS-LINE-CENTS * WS-TAX-PERCENT
              ADD WS-TAX-CENTS TO WS-LINE-CENTS
              ADD WS-LINE-CENTS TO WS-TOTAL-CENTS
           END-PERFORM

           MOVE INVOICE-ID TO OUT-INVOICE-ID
           MOVE WS-TOTAL-CENTS TO OUT-TOTAL
           MOVE ITEM-COUNT TO OUT-ITEM-COUNT
           IF WS-TOTAL-CENTS >= 100000
              MOVE "H" TO OUT-FLAG
           ELSE
              MOVE "L" TO OUT-FLAG
           END-IF.
