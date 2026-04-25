       01  INVOICE-RECORD.
           05 INVOICE-ID             PIC X(6).
           05 ITEM-COUNT             PIC 9(2).
           05 LINE-ITEM OCCURS 4 TIMES.
              10 ITEM-QTY            PIC 9(2).
              10 ITEM-PRICE          PIC 9(4)V99.
              10 TAX-CODE            PIC X.
